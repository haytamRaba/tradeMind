# TradeMind

TradeMind is an AI-assisted stock research and paper-trading platform. The long-term design keeps market calculations and risk controls deterministic while AI interprets validated evidence and explains results.

## Current phase

Phase 2 adds a functional Research Agent and a risk-limited paper Trading Agent on top of the Phase 1 market-data platform. The agents run locally without an OpenAI key; an optional OpenAI Responses API call can explain computed research evidence. AI output never changes a quantitative signal or bypasses trading controls.

All order execution is simulated. No live broker integration is enabled.

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
| `OPENAI_API_KEY` | unset | Optional key for Research Agent narration; never needed for calculations or paper trading |
| `OPENAI_MODEL` | `gpt-6.2-sol` | Model used only for report narration when a key is configured |
| `PAPER_INITIAL_CASH` | `100000` | Starting cash for the default simulated portfolio |
| `MAX_RISK_PER_TRADE_PCT` | `0.01` | Maximum portfolio equity risked on one new order |
| `MAX_POSITION_PCT` | `0.10` | Maximum equity allocated to a single ticker |
| `MAX_PORTFOLIO_EXPOSURE_PCT` | `0.50` | Maximum total long exposure |
| `MAX_DAILY_LOSS_PCT` | `0.05` | Stops new buys after realized daily losses reach this limit |
| `MAX_OPEN_POSITIONS` | `10` | Maximum number of simultaneous positions |

Yahoo Finance does not require a TradeMind API key. `OPENAI_API_KEY` is optional and is used only to narrate computed research evidence. It is never required to calculate indicators or execute simulated paper trades.

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

### Research and trading agents

```text
POST /api/v1/agents/research/{ticker}?period=1y&interval=1d
POST /api/v1/agents/trading/{ticker}/execute
GET  /api/v1/paper-trading/portfolio
GET  /api/v1/paper-trading/orders
POST /api/v1/paper-trading/monitor
```

Research refreshes market history, validates it, calculates deterministic technical indicators, and evaluates the configured strategy set. The response includes the signal, indicator values, strategy votes, proposed entry/stop/target levels, and a short explanation. An optional model can narrate this evidence; it cannot alter the calculations or signal. Insufficient history produces an `INSUFFICIENT_DATA` result.

Trading accepts the latest research report and places only simulated orders. New buy orders require a stop price and are checked against per-trade risk, position size, total exposure, daily realized loss, and open-position limits. The default simulated account starts with `$100,000`; configure paper limits with the environment variables above. The monitor refreshes open tickers and checks stored bars against stop-loss and take-profit levels.

Paper fills use the supplied reference price and currently do not model fees, spread, slippage, partial fills, or intraday stop ordering. Sell signals close the full simulated position. The API has no authentication yet and is intended for local development.

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
  agents/       Research and paper trading workflows
  analysis/     Deterministic technical indicators
  database/     SQLAlchemy models, repositories, and session factory
  execution/    Paper broker and order persistence
  market_data/  Provider contract, Yahoo provider, validation, and workflow service
  risk/         Paper-trading limits and position sizing
  strategies/   Deterministic signal strategies and consensus engine
  config.py     pydantic-settings configuration
  main.py       FastAPI application entry point
migrations/     Alembic environment and versioned schema changes
tests/          Offline unit and API tests
```

Reserved for later phases:

```text
app/memory/       Agent memory
app/reports/      Report generation
app/tasks/        Scheduled analysis and monitoring
```

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
- Technical indicators, strategy consensus, research orchestration, and optional narration
- Paper portfolio persistence, idempotent orders, risk rejection, position accounting, and protective exits
- Research, execution, portfolio, order, and monitoring API responses

## Docker Compose

Docker Compose provides the API, PostgreSQL, and a one-shot migration service. PostgreSQL data is stored in the named `postgres_data` volume. The API starts only after the database is healthy and migrations have completed.

Development with source mounts and Uvicorn reload:

```bash
copy .env.example .env
docker compose -f compose.yaml -f compose.dev.yaml up --build
```

Production-style background stack:

```bash
docker compose -f compose.yaml -f compose.prod.yaml up --build -d
```

Set a strong `DB_PASSWORD` in `.env` before using the production override. The API is available at `http://localhost:8000/docs` unless `APP_PORT` is changed in `.env`.

Useful commands:

```bash
docker compose ps
docker compose logs -f api
docker compose down
docker compose down -v
```

`docker compose down -v` also deletes the PostgreSQL volume and all local data.

For an internet-facing deployment, terminate TLS at a reverse proxy and do not expose the API publicly until authentication, authorization, rate limiting, and audit logging are implemented. No live-money trading capability is implemented.

## Roadmap

Planned supporting work, in priority order:

1. Structured logging, request IDs, and audit logging
2. Authentication, authorization, request validation, and rate limiting
3. Skills registry with permissions and execution metrics
4. Fundamental data and broader quantitative analysis
5. Frontend dashboard backed by the real API contracts

## Release v1

TradeMind v1 provides validated Yahoo Finance market data, deterministic technical research, and risk-limited simulated paper trading. Optional AI narration explains research evidence but cannot direct or execute orders. All trading is simulated; live brokerage, authentication, and production deployment controls are outside this release.
