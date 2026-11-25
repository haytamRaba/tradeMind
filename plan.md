# TradeMind Agent Pipeline - Build Plan

## Project Overview

TradeMind is a FastAPI-based trading agent platform with:
- **Market Data Service**: Fetches, validates, and persists OHLCV data from Yahoo Finance
- **Research Agent**: Analyzes market data using 4 technical strategies (MA Crossover, RSI Mean Reversion, MACD Momentum, Trend Following)
- **Trading Agent**: Executes paper trades with deterministic risk validation
- **Risk Engine**: Position sizing, daily loss limits, max positions, exposure caps
- **Paper Trading**: Simulated broker with idempotent orders and protective stop monitoring

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Market Data    │────▶│  Research Agent │────▶│  Trading Agent  │
│  (Yahoo Finance)│     │  (4 Strategies) │     │  (Paper Broker) │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │                       │
        ▼                       ▼                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  PostgreSQL/    │     │  Strategy       │     │  Risk Validator │
│  SQLite (test)  │     │  Engine         │     │  Position Sizer │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## Current State (Phase 1 Complete)

✅ **Completed Components:**
- FastAPI app with market data & agent endpoints
- Yahoo Finance provider with validation
- SQLite/PostgreSQL dual-dialect repositories (idempotent upserts)
- 4 technical strategies + consensus engine
- Research agent with deterministic + OpenAI narration
- Trading agent with paper broker
- Risk validator + position sizer
- 34 passing tests (unit + API)
- Alembic migrations for market data + paper trading

## Phase 2: Agent Pipeline Enhancement (In Progress)

### 2.1 Runnable CLI Demo Script
- [ ] Create `scripts/run_agent_pipeline.py` using SQLite in-memory
- [ ] Demonstrate full flow: seed data → research → execute → monitor
- [ ] Add argparse for ticker/period/interval
- [ ] Output structured JSON + human-readable logs

### 2.2 Test Enhancement
- [ ] Add integration test for full pipeline (data→research→trade→monitor)
- [ ] Add test for protective stop triggering
- [ ] Add test for daily loss limit enforcement
- [ ] Add test for idempotent replay behavior

### 2.3 Actions Demo Output
- [ ] Run pipeline and capture output to `actions_demo.txt`
- [ ] Document each step with timestamps and decisions

## Phase 3: Production Hardening

### 3.1 Database & Migrations
- [ ] Verify Alembic migrations work with PostgreSQL
- [ ] Add indexes for common query patterns
- [ ] Add connection pooling configuration

### 3.2 Error Handling & Observability
- [ ] Structured logging (JSON format)
- [ ] Request tracing (correlation IDs)
- [ ] Health check endpoints with dependency status
- [ ] Metrics exposure (Prometheus format)

### 3.3 Security
- [ ] Input sanitization on all endpoints
- [ ] Rate limiting on market data endpoints
- [ ] API key authentication for agent endpoints
- [ ] Secrets management (no hardcoded credentials)

### 3.4 Deployment
- [ ] Dockerfile with multi-stage build
- [ ] docker-compose.yml for local dev (PostgreSQL + app)
- [ ] GitHub Actions CI pipeline
- [ ] Production deployment docs

## Phase 4: Advanced Features

### 4.1 Strategy Expansion
- [ ] Add Bollinger Bands strategy
- [ ] Add Volume-Weighted strategies
- [ ] Strategy backtesting framework
- [ ] Strategy parameter optimization

### 4.2 Portfolio Management
- [ ] Multi-portfolio support
- [ ] Portfolio rebalancing agent
- [ ] Risk parity allocation
- [ ] Correlation-based position limits

### 4.3 Real-time & Streaming
- [ ] WebSocket market data feed
- [ ] Real-time position monitoring
- [ ] Alert system (email/Slack/Discord)
- [ ] Scheduled research runs (cron/APScheduler)

### 4.4 LLM Integration
- [ ] Structured output parsing for trade rationale
- [ ] Multi-agent debate for consensus
- [ ] News sentiment integration
- [ ] Fundamental analysis agent

## Phase 5: Streamlit Frontend

### 5.1 Core Dashboard Pages
- [ ] **Market Data Explorer** - Search tickers, view OHLCV charts with indicators (SMA, RSI, MACD, ATR)
- [ ] **Research Agent UI** - Run analysis, view strategy votes, evidence, and AI narration
- [ ] **Paper Trading Dashboard** - Portfolio overview, positions, P&L, order history
- [ ] **Risk Monitor** - Exposure limits, daily loss tracker, position sizing calculator

### 5.2 Interactive Features
- [ ] Real-time chart updates (Plotly) with indicator overlays
- [ ] One-click research run with progress indicator
- [ ] Trade execution modal with risk preview (quantity, stop, target)
- [ ] Historical backtest visualizer for strategies
- [ ] WebSocket live price feed for watched tickers

### 5.3 Architecture Integration
- [ ] Streamlit app calls FastAPI endpoints via httpx
- [ ] Shared config (Settings) between FastAPI and Streamlit
- [ ] Authentication via API key in sidebar
- [ ] Session state for multi-page navigation
- [ ] Caching with st.cache_data for market data calls

### 5.4 File Structure Addition
```
tradeMind/
├── frontend/                    # Streamlit app (NEW)
│   ├── app.py                   # Main entry point
│   ├── pages/
│   │   ├── 1_📊_Market_Data.py
│   │   ├── 2_🔬_Research.py
│   │   ├── 3_📈_Trading.py
│   │   ├── 4_⚠️_Risk.py
│   │   └── 5_📜_History.py
│   ├── components/
│   │   ├── charts.py            # Plotly chart components
│   │   ├── forms.py             # Reusable form components
│   │   └── metrics.py           # KPI cards, progress bars
│   ├── services/
│   │   ├── api_client.py        # httpx client for FastAPI
│   │   └── cache.py             # Streamlit caching wrappers
│   └── config.py                # Streamlit-specific settings
├── requirements.txt             # Add streamlit, plotly
└── docker-compose.yml           # Add streamlit service
```

## File Structure

```
tradeMind/
├── app/
│   ├── agents/
│   │   ├── research_agent/     # Research pipeline
│   │   ├── trading_agent/      # Paper trading execution
│   │   └── shared/             # LLM narrator
│   ├── analysis/               # Technical indicators
│   ├── api/                    # FastAPI routes & schemas
│   ├── config.py               # Pydantic settings
│   ├── database/               # Models, repositories, session
│   ├── execution/              # Paper broker, order repos
│   ├── market_data/            # Provider, validation, service
│   ├── risk/                   # Limits, sizing, validator
│   └── strategies/             # 4 strategies + engine
├── frontend/                    # Streamlit app (NEW)
│   ├── app.py                   # Main entry point
│   ├── pages/                   # Multi-page dashboard
│   ├── components/              # Reusable UI components
│   ├── services/                # API client, caching
│   └── config.py                # Streamlit settings
├── migrations/                  # Alembic migrations
├── scripts/                     # CLI entry points
├── tests/                       # Unit + API tests
├── .env                         # Local config
├── requirements.txt
└── plan.md                      # This file
```

## Key Technical Decisions

| Decision | Rationale |
|----------|-----------|
| SQLite for tests, PostgreSQL for prod | Fast CI, production parity |
| Idempotent upserts (ON CONFLICT) | Safe re-fetch, no duplicates |
| Deterministic research first | Reproducible, testable, no API costs |
| Whole-share position sizing | Realistic paper trading |
| Consensus voting (2/4 strategies) | Reduces false signals |
| Idempotency keys on all orders | Safe retry, exactly-once semantics |

## Next Steps (Priority Order)

1. **Create runnable demo script** (`scripts/run_agent_pipeline.py`) ✅
2. **Enhance tests** with integration coverage
3. **Run pipeline** and save output to `actions_demo.txt` ✅
4. **Add Docker** support for local development
5. **Set up CI/CD** with GitHub Actions
6. **Document API** with OpenAPI/Swagger improvements
7. **Build Streamlit frontend** (Phase 5) - Market Data, Research, Trading, Risk dashboards

## Commands Reference

```bash
# Run tests
source .venv/Scripts/activate && python -m pytest tests/ -v

# Run demo pipeline
python scripts/run_agent_pipeline.py --ticker MSFT --period 1mo --interval 1d

# Start API server
source .venv/Scripts/activate && uvicorn app.main:app --reload

# Start Streamlit frontend (in separate terminal)
source .venv/Scripts/activate && streamlit run frontend/app.py

# Run migrations
alembic upgrade head

# Create migration
alembic revision --autogenerate -m "description"

# Docker compose (all services)
docker-compose up -d
```

## Dependencies

```
# Backend (FastAPI)
fastapi
uvicorn
sqlalchemy
psycopg2-binary
pydantic
pydantic-settings
python-dotenv
httpx
yfinance
pandas
numpy
alembic
pytest
pytest-asyncio

# Frontend (Streamlit)
streamlit
plotly
```