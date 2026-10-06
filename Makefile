.PHONY: up down seed test lint

up:
	@test -f .env || cp .env.example .env
	docker compose up --build -d

down:
	docker compose down

seed:
	docker compose exec api python -m app.seed.run

test:
	cd apps/api && uv run pytest -q
	cd apps/web && pnpm exec vitest run

lint:
	cd apps/api && uv run ruff check . && uv run mypy app
	cd apps/web && pnpm exec tsc -b && pnpm lint
