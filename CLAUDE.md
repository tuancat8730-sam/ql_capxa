# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

Use the `Makefile` at the root for common development tasks.

### General
- **Start services**: `make up` (Starts Docker containers for the API and other dependencies)
- **Stop services**: `make down` (Stops and removes Docker containers)
- **Seed database**: `make seed` (Populates the database via the API's seed script)

### API (Python / FastAPI)
- **Run tests**: `cd apps/api && uv run pytest -q`
- **Linting & Type Checking**: `cd apps/api && uv run ruff check . && uv run mypy app`
- **Database Migrations**: Managed via `alembic` within `apps/api/alembic`

### Web (TypeScript / React / Vite)
- **Run tests**: `cd apps/web && pnpm exec vitest run`
- **Linting & Type Checking**: `cd apps/web && pnpm exec tsc -b && pnpm lint`
- **E2E Tests**: Managed via Playwright in `apps/web/e2e`

## Architecture & Structure

This project is structured as a monorepo containing a backend API and a frontend web application.

### Core Structure
- `apps/api`: The backend service.
    - `app/core`: Contains shared configuration, database connection logic, security headers, and RBAC (Role-Based Access Control) logic.
    - `app/models`: SQLAlchemy database models.
    - `app/schemas`: Pydantic models for request/response validation.
    - `app/routers`: API endpoint definitions (FastAPI).
    - `app/services`: **Business Logic Layer**. Most domain-specific logic (finance, plans, storage, notifications) resides here.
    - `app/worker.py`: Background task processing (likely using Celery or similar).
- `apps/web`: The frontend application.
    - Uses Vite, React, and TypeScript.
    - `src/`: Core UI components and logic.
    - `e2e/`: Playwright end-to-end tests.
- `infra/`: Infrastructure definitions (e.g., Terraform, CloudFormation).
- `deploy/`: Scripts for VPS deployment and environment setup.
- `scripts/`: Utility scripts for both the root project and individual sub-apps.

### Key Technologies
- **Backend**: Python, FastAPI, SQLAlchemy, Alembic, `uv` (package management).
- **Frontend**: TypeScript, React, Vite, `pnpm` (package management).
- **Infrastructure**: Docker, Docker Compose, MinIO (object storage).
