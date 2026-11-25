# TradeMind Project Plan

## Purpose

This document tracks the planned development of TradeMind beyond the current v1 release. Work should build on the existing market-data, research, and paper-trading services instead of duplicating them. Live trading remains out of scope until its safety, authorization, and operational requirements are separately designed and approved.

## Current release: v1

**Status:** Complete

### Delivered

- Yahoo Finance market-data retrieval, validation, persistence, and API access.
- Deterministic technical indicators and strategy consensus for research reports.
- Optional AI narration that cannot alter calculated values or signals.
- Simulated paper orders, portfolio persistence, idempotency, risk checks, and protective-level monitoring.
- Offline tests and Alembic migrations for market data and paper-trading records.

### Current boundaries

- Orders are simulated and fill at a reference price; fees, spread, slippage, and partial fills are not modeled.
- The API has no authentication or authorization.
- Fundamental data, scheduled tasks, and a user interface are not included.

## Next milestones

### Phase 3: Reliability and local deployment

**Goal:** Make development and deployment repeatable and easier to operate.

**Planned work:**

- Add continuous integration for the test suite, migration checks, linting, and type checks.
- Add Docker and Docker Compose for the API and PostgreSQL.
- Add structured logs, request identifiers, and audit events for paper orders and risk decisions.
- Document backup, migration, and local troubleshooting procedures.

**Completion criteria:**

- CI validates changes without contacting Yahoo Finance or an LLM provider.
- A clean checkout can start the API and database using documented commands.
- Order and risk decisions can be traced through logs without recording secrets.

### Phase 4: API access controls

**Goal:** Protect API access before exposing the service beyond local development.

**Planned work:**

- Define an authentication and authorization model.
- Restrict portfolio and order operations to authorized users.
- Add request limits and consistent input validation.
- Add security-focused tests for allowed and denied operations.

**Completion criteria:**

- Protected routes reject unauthenticated and unauthorized requests.
- Access-control behavior is covered by automated tests and documented configuration.

### Phase 5: Broader research and strategy support

**Goal:** Expand research coverage while keeping calculations and trading decisions auditable.

**Planned work:**

- Define data-provider interfaces and data-quality expectations for fundamental data.
- Add fundamental metrics and broader quantitative analysis as independent modules.
- Evaluate strategy inputs and outcomes with reproducible historical data.
- Track report inputs and strategy versions so results can be explained later.

**Completion criteria:**

- New inputs have validation, persistence rules, and offline tests.
- Research reports identify the data and strategy inputs used to produce each result.

### Phase 6: Skills and scheduled workflows

**Goal:** Add controlled, observable automation for supported research tasks.

**Planned work:**

- Define a skills registry with explicit permissions and input/output contracts.
- Add scheduled analysis and monitoring tasks with retry and failure handling.
- Record execution status and metrics without allowing a skill to bypass risk checks.

**Completion criteria:**

- Each skill declares its permissions and is tested for denied operations.
- Scheduled runs are observable, retry safely, and do not create duplicate orders.

### Phase 7: User interface

**Goal:** Provide a dashboard backed by the documented API contracts.

**Planned work:**

- Display market history and research reports.
- Display simulated cash, positions, orders, and risk rejections.
- Show clear simulated-trading labels and current portfolio configuration.

**Completion criteria:**

- Dashboard views use the existing API contracts and handle provider or API errors clearly.
- Users can distinguish simulated results from live market data.

## Development principles

- Keep provider, validation, strategy, risk, persistence, and API responsibilities separate.
- Prefer deterministic business logic; treat AI output as explanatory unless a future design explicitly establishes otherwise.
- Never bypass risk validation for an order.
- Do not add secrets to source control; use environment configuration and placeholders.
- Add offline tests for new behavior and verify schema changes with migrations.
- Keep each change reviewable, update documentation with user-visible behavior, and use focused Conventional Commits.

## Deferred decisions

- Whether and how any live brokerage integration could be authorized and supervised.
- User tenancy, account isolation, and deployment architecture.
- Supported fundamental-data providers and their licensing constraints.
- Production availability, monitoring, and recovery targets.
