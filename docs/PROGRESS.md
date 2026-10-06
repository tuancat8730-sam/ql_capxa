# Progress (M0–M8)

Source of truth: `docs/SPEC.md`. User instruction: implement M0–M8 in order, one commit per task, TDD for section 7 rules.
Decisions: no Terraform; `package_access` table for sensitive docs; git remote added but never push without asking; pnpm via corepack (`export PATH=$HOME/.local/bin:$PATH`); React 18 pinned; `data_documents/` is real data and is git-ignored.

## M0 – Khung dự án
- [x] API skeleton: config, error envelope, `/api/v1/health` (3 tests green)
- [x] Web skeleton: Vite + Tailwind v4 tokens, AppShell (BottomNav/Sidebar), i18n vi, `format.ts` (9 tests green)
- [x] docker-compose (db, minio, mailpit, api, worker, web), Makefile, `.env.example`
- [x] Alembic init + worker entrypoint
- [x] CI (GitHub Actions); pre-commit still pending
- [x] Playwright 3 projects config; PWA manifest stub deferred to M5

## M1 – Xác thực và phân quyền
- [x] users + audit_log tables, migration 0001 (up/down/up verified on empty DB)
- [x] argon2, JWT access 15m + refresh 7d (HttpOnly cookie), token_version revocation
- [x] lock 15 min after 5 failed logins; forced password change on first login
- [x] SPEC section 8 matrix as data (`core/rbac.py`) with full truth-table test; `require()` dependency
- [x] /auth, /users (admin only), /audit-log (admin, director); audit rows for login and user changes
- [x] Web: login, change password, profile/logout, admin users (cards on phone, table from md), route guards
- [x] `make seed` creates first admin (`SEED_ADMIN_EMAIL`/`SEED_ADMIN_PASSWORD`, else generated and printed once)
- Tests: api 325 (95% coverage), web 29. Deviation: audit rows are written by an explicit `audit.record()` call in each router rather than a generic middleware, so diffs are precise and secrets are scrubbed.
- Note: sensitive-document access (`package_access`) is deferred to M4 where documents exist; the matrix already encodes the "S" (assigned only) level.

## M2–M8
Not started.
