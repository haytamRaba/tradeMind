# TradeMind

TradeMind is an AI-assisted stock research and paper-trading platform. The long-term design keeps market calculations and risk controls deterministic while AI interprets validated evidence and explains results.

## Current phase

Phase 1 implements the market-data foundation:

- Yahoo Finance retrieval through `yfinance`
- OHLCV validation and UTC normalization
- PostgreSQL/SQLite persistence with idempotent upserts
- A versioned FastAPI market-data API
- An Alembic migration for stock and historical-price tables
- Offline tests using SQLite and mocked Yahoo responses

The research agent, trading agent, risk controls, strategies, paper-trading engine, background tasks, authentication, observability, Docker/CI, and frontend are **not implemented yet**. Their empty module directories are reserved architecture, not working features.

## Requirements

- Python 3.10+
- PostgreSQL 14+ for local/production persistence
- No Yahoo Finance API key is required

## Setup

### 1. Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. Configure the environment

```bash
copy .env.example .env
```

On macOS/Linux, use `cp .env.example .env` instead.

Edit `.env` before starting the API or running migrations. At minimum, set the database user, password, and name.

### 4. Prepare PostgreSQL

Create a database and role matching `.env`, for example:

```sql
CREATE USER trademind WITH PASSWORD 'change-me';
CREATE DATABASE trademind OWNER trademind;
```

Use a strong password outside local development. Do not commit `.env`.

Alternatively, set `DATABASE_URL` and skip the individual `DB_*` fields.

### 5. Apply migrations

```bash
python -m alembic upgrade head
```

`alembic.ini` points to the root `migrations/` directory. `migrations/env.py` loads the database URL from `app.config.Settings`, so the `sqlalchemy.url` value in `alembic.ini` is only a placeholder.

### 6. Start the API

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Interactive API docs are available at `http://localhost:8000/docs`. The OpenAPI document is at `http://localhost:8000/openapi.json`.

## Environment variables

| Variable | Default | Description |
| --- | --- | --- |
| `APP_HOST` | `0.0.0.0` | Uvicorn bind host |
| `APP_PORT` | `8000` | Uvicorn bind port |
| `APP_ENV` | `development` | Environment name |
| `LOG_LEVEL` | `INFO` | Python logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` |
| `DB_HOST` | `localhost` | PostgreSQL host; use `db` when a container network provides that service |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_USER` | `trademind` | PostgreSQL role |
| `DB_PASSWORD` | `change-me` | PostgreSQL password; override in every non-local environment |
| `DB_NAME` | `trademind` | PostgreSQL database |
| `DATABASE_URL` | unset | Optional full SQLAlchemy URL override |
| `PROJECT_NAME` | `TradeMind` | FastAPI title |
| `API_V1_PREFIX` | `/api/v1` | API route prefix |

Yahoo Finance does not require a TradeMind API key. Broker credentials, LLM keys, and live-trading settings are not implemented and must not be added until those subsystems exist with explicit authorization controls.

## API

All routes are mounted under `/api/v1`.

### Health

```text
GET /api/v1/health
```

Returns a static liveness response.

### Fetch and store market data

```text
GET /api/v1/market-data/{ticker}?period=1mo&interval=1d
```

Fetches history from Yahoo Finance, validates it, persists valid bars, and returns the normalized rows plus data-quality issues.

Common query parameters:

- `period`: `1d`, `5d`, `1mo`, `3mo`, `6mo`, `1y`, `2y`, `5y`, `10y`, `ytd`, `max`
- `interval`: `1m`, `2m`, `5m`, `15m`, `30m`, `60m`, `90m`, `1h`, `1d`, `5d`, `1wk`, `1mo`, `3mo`

Response shape:

```json
{
  "ticker": "MSFT",
  "period": "1mo",
  "interval": "1d",
  "rows_fetched": 21,
  "rows_persisted": 21,
  "issues": [],
  "data": [
    {
      "timestamp": "2025-01-02T00:00:00+00:00",
      "open": 10.0,
      "high": 12.0,
      "low": 9.0,
      "close": 11.0,
      "volume": 1000
    }
  ]
}
```

### Fetch and store the latest bar

```text
GET /api/v1/market-data/{ticker}/latest
```

Uses the provider's latest-bar lookup when available and returns a single normalized bar.

### Retrieve stored history

```text
GET /api/v1/market-data/{ticker}/history?start=2025-01-01T00:00:00Z&end=2025-01-31T23:59:59Z
```

Returns stored bars in ascending timestamp order. `start` and `end` must be supplied together; when both are present, that range is refreshed from Yahoo Finance before the stored history is returned.

Response shape:

```json
{
  "ticker": "MSFT",
  "count": 2,
  "data": []
}
```

### Error responses

| Status | Meaning |
| --- | --- |
| `404` | Invalid ticker, empty provider response, or no stored history |
| `422` | Invalid date, interval, period, or rejected data-quality issues |
| `429` | Yahoo Finance rate limit |
| `502` | Provider/network/service failure |
| `500` | Unexpected server error |

Validation errors include structured issues with `ticker`, `timestamp`, `severity`, `rule`, `value`, and `fix_applied` fields.

## Data behavior

- Ticker symbols are normalized to uppercase and limited to 12 characters.
- Yahoo Finance responses are converted to canonical lowercase `open`, `high`, `low`, `close`, `volume` columns.
- Timestamps are normalized to UTC.
- Invalid, missing, non-finite, non-positive-price, internally inconsistent OHLC, and invalid-volume rows are rejected and reported.
- Duplicate timestamps keep the first row and are reported as a warning.
- Prices and volume are never silently filled, clamped, or repaired.
- Repeated fetches update the row identified by `(stock_id, timestamp)` instead of creating duplicates.

## Project layout

```text
app/
  api/          FastAPI routes, dependencies, and response schemas
  database/     SQLAlchemy models, repositories, and session factory
  market_data/  Provider contract, Yahoo provider, validation, and workflow service
  config.py     pydantic-settings configuration
  main.py       FastAPI application entry point
migrations/     Alembic environment and versioned schema changes
tests/          Offline unit and API tests
```

Reserved for later phases:

```text
app/agents/       Research and trading agents
app/analysis/     Technical, fundamental, and regime analysis
app/execution/    Broker interface, paper trading, and order management
app/memory/       Agent memory
app/reports/      Report generation
app/risk/         Risk limits and pre-trade validation
app/strategies/   Strategy implementations
app/tasks/        Scheduled analysis and monitoring
```

These directories currently contain placeholders only.

## Testing

Run the full offline suite:

```bash
python -m pytest
```

Or with concise output:

```bash
python -m pytest -q
```

The suite uses an in-memory SQLite database and mocked Yahoo Finance responses. It does not require OpenAI credits, broker credentials, a running PostgreSQL server, or network access.

Current test coverage includes:

- Yahoo provider argument passing, normalization, company info, and typed errors
- OHLCV validation and rejection rules
- Service persistence and duplicate-bar updates
- Latest-bar handling
- API route shapes, OpenAPI paths, and error mapping

## Docker and deployment

Docker Compose and production deployment automation are **not yet configured**. For now, run PostgreSQL separately and start the API with Uvicorn as shown above.

For a production deployment:

1. Set `APP_ENV=production`.
2. Provide a strong `DB_PASSWORD` or a complete `DATABASE_URL`.
3. Run `python -m alembic upgrade head` before starting the API.
4. Run Uvicorn behind a reverse proxy with TLS.
5. Do not expose the API publicly until authentication, authorization, rate limiting, and audit logging are implemented.

No live-money trading capability is implemented.

## Roadmap

Planned supporting work, in priority order:

1. CI for linting, tests, type checks, and migration validation
2. Docker and Docker Compose for API, PostgreSQL, and optional Redis
3. Structured logging, request IDs, and audit logging
4. Authentication, authorization, request validation, and rate limiting
5. Research Agent and Trading Agent workflows with mocked LLM tests
6. Skills registry with permissions and execution metrics
7. Deterministic risk validation, paper trading, and order idempotency
8. Frontend dashboard backed by the real API contracts
