# Progress (M0–M8)

Source of truth: `docs/SPEC.md`. User instruction: implement M0–M8 in order, one commit per task, TDD for section 7 rules.
Decisions: no Terraform; `package_access` table for sensitive docs; git remote added but never push without asking; pnpm via corepack (`export PATH=$HOME/.local/bin:$PATH`); React 18 pinned; `data_documents/` is real data and is git-ignored.

## M0 – Khung dự án
- [x] API skeleton: config, error envelope, `/api/v1/health` (3 tests green)
- [x] Web skeleton: Vite + Tailwind v4 tokens, AppShell (BottomNav/Sidebar), i18n vi, `format.ts` (9 tests green)
- [ ] docker-compose (db, minio, mailpit, api, worker, web), Makefile, `.env.example`
- [ ] Alembic init + worker entrypoint
- [ ] CI (GitHub Actions), pre-commit
- [ ] Playwright 3 projects (mobile/tablet/desktop), PWA manifest stub

## M1–M8
Not started.
