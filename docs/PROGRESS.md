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

## M2 – Dự án, gói thầu, hợp đồng
- [x] organizations, projects, packages, contracts, contract_parties/items/amendments + migration 0002 (up/down/up verified)
- [x] SPEC 7.5 consistency rules (`services/rules.py`, 30 tests: ok / boundary / violation each), shown on every contract response
- [x] /project, /packages (+overview), /contracts and child CRUD; matrix-based 403 tests for all 8 roles
- [x] planned end date = start + duration - 1, recomputed on edit unless `end_date_override`
- [x] seed from SPEC 14 (8 packages, 7 contracts, parties); unknown values stay NULL, questions in `docs/OPEN_QUESTIONS.md`
- [x] Web: package list (cards on phone, table from md, health filter chips), package detail (tabs via `?tab=`, accordion overview, contract tab with flags)
- AC check: flags appear on Gói 02 (duration, treasury account, lump-sum vs price adjustment) and Gói 04 (end date). Gói 01 is flagged too (SPEC 14.3 lists its 18/9 vs 17/9 discrepancy); Gói 06 shows an info-level override.
- Tests: api 408 (97% coverage), web 35.
- Deferred: shadcn/ui is not used (plain Tailwind components); MoneyInput/BottomSheet generic components arrive with the first money form in M3.

## M3 – Bảo lãnh và thanh toán
- [x] guarantees, payments, disbursement_plan + migration 0003 (up/down/up verified)
- [x] SPEC 7.2 statuses derived from expiry (`expiring`/`expired` never stored); `services/guarantee_rules.py` (36 tests): GUARANTEE_EXPIRING, ADVANCE_GUARANTEE_SHORT, GUARANTEE_MISSING, reused by the M7 alert engine
- [x] guarantee CRUD, payment CRUD + workflow (planned → requested → approved → paid via `mark-paid`; only approvers may approve/reject), `GET /guarantees`, `GET /payments`, `GET/PUT /project/disbursement-plan`
- [x] seed from SPEC 14.4/14.5 (ABBank, TPBank, BIDV, 2 `missing` rows, 5 planned payments)
- [x] Web: `/contracts` (guarantees, soonest expiry first, critical findings banner, status filter), `/payments` (workflow by role, mark-paid sheet, disbursement plan editor), package detail guarantees + payments tabs; shared `BottomSheet`, `MoneyInput`, client-side permission mirror
- AC check: with "today" = 05/11/2026 the Package 05 TPBank/BIDV guarantees are `expiring` (8 days) and raise `ADVANCE_GUARANTEE_SHORT` (critical, needed until 19/11). With today's real date (06/10/2026) they are still `valid` because 13/11 is 38 days away; the test pins the date.
- Tests: api 494, web 55.
- Deviations: added list endpoints `GET /guarantees` and `GET /payments` and `GET /contracts/{id}/guarantee-checks` (not in the SPEC table) because the `/contracts` and `/payments` screens need cross-contract views. "Outstanding advance" = contract advance − paid recovery payments.

## M4 – Kho tài liệu
- [x] documents, checklist_templates, checklist_items, package_access + migration 0004 (creates `pg_trgm`, `unaccent`; up/down/up verified)
- [x] `Storage` interface: `S3Storage` (boto3, presigned PUT/GET, browser-facing endpoint separate from the internal one) and `MemoryStorage` for tests
- [x] upload flow: `upload-url` → direct PUT → `POST /documents` confirm (object exists, size and key match, SHA-256 computed server-side, duplicate blocked per package); versions; soft delete; PATCH metadata
- [x] text extraction (pdf via pypdf, docx, xlsx, txt) in a background task; scanned PDFs → `needs_ocr`; broken files → `failed` but the upload is kept
- [x] diacritic-free search (`unaccent` + `tsvector` + escaped `ILIKE`); "bao lanh tam ung" finds "Bảo lãnh tạm ứng"
- [x] sensitive documents: forced for sensitive packages; admin/director see all, procurement/technical only with `package_access`; others get a redacted stub in lists and nothing in search; every download is audited
- [x] checklist: templates from SPEC 4.7 (28 goods / 8 consulting items), instantiate, auto-link on upload and version change, N/A handling, overdue flag, completion % on the package card
- [x] Web: `/documents` (search, filters, multi-file upload with progress and retry, camera capture with ≤1600 px compression, full-screen PDF/image preview, version upload), package "Hồ sơ" tab (checklist + admin-only access section), route-level code splitting (initial JS ≈ 69 KB gzip)
- AC check: 50 MB upload through a presigned URL verified over real HTTP (moto S3 server); search with and without diacritics; viewer never sees sensitive documents.
- Tests: api 600+ (97% coverage), web 77.
- Deviations / notes: MinIO's image could not be pulled in this environment, so S3 behaviour is verified against moto, not MinIO itself (`make up` + a manual upload is still worth doing once). PDF text uses `pypdf` (pure Python) instead of `pdftotext`, so no poppler dependency in the image. Browser does not hash files; the API computes SHA-256 from the stored object. Extraction runs as an in-process background task; moving it to the worker queue is a later optimisation. Metadata edit (PATCH) has an API but no UI yet; the admin access UI lists users through `/users`, so directors manage access through the API only.

## M5 – Tiến độ
- [x] stage_plans, tasks, progress_logs + migration 0005 (up/down/up verified)
- [x] weighted package progress (10/20/40/20/10, editable), current stage, derived `delayed` status (never stored), stage date validation
- [x] tasks: CRUD, dependency cycle detection, "all tasks done → suggest closing the stage" (the user confirms; the API never closes it silently)
- [x] daily logs: one per package/day/author, `Idempotency-Key` replay returns the first result (200), duplicate day → 409 `log_exists` with the existing id, attachments must be documents of the same package
- [x] `GET /dashboard/timeline` (stages + contract bars on one axis), `GET /export/ql06.xlsx` (Vietnamese headers, real dates/money formats, late cells in red, audited)
- [x] Web: package "Tiến độ" tab (stage cards + edit sheet, Kanban with drag on lg and a status select everywhere), `/progress` (list timeline on phones, SVG Gantt from lg with drag/resize by pointer and by arrow keys, today and contract-end markers, week/month zoom, QL-06 download), `/daily-log` (mobile-first form, camera capture, ≤10 photos, autosaved drafts, last package remembered, sticky submit)
- [x] Offline (SPEC 15.7): IndexedDB drafts + outbox, client UUID as Idempotency-Key, photos uploaded once and remembered, auto-sync on start / `online` event / every 30 s, per-item status "Chưa gửi / Đang gửi / Đã gửi / Lỗi – thử lại", conflict resolution (merge / overwrite / discard), offline banner
- [x] PWA (SPEC 15.6): manifest (vi, 192/512/maskable), Workbox service worker (app shell precached, GET API stale-while-revalidate, writes never cached), install prompt once, "new version" toast; icons generated by `scripts/make-icons.py`
- AC check: dragging a Gantt bar PATCHes the stage dates and the timeline follows; the contract end date follows start + duration − 1 with override (M2); `.xlsx` is read back with openpyxl in tests.
- Tests: api 679 (97% coverage), web 122.
- Deviations / notes: seed marks S2 done only for packages with a signed contract and S3 dates from the contract; everything else stays empty (OPEN_QUESTIONS 21). Playwright, Lighthouse and real-device checks are not run yet (M8). QL-06 columns are filled from document dates and the contract signing date; "Số nhà thầu" and "Vướng mắc" have no data source yet.

## M6 – Rủi ro và vướng mắc
- [x] risks, issues (+ issue_events), holidays, meetings, action_items, change_requests + migration 0006 (up/down/up verified)
- [x] risk register: score computed by the server (CHECK constraint keeps it honest), 5×5 matrix with the ids per cell, only the director closes or reopens, 14-day review reminder + `POST /risks/{id}/review`
- [x] issues: 3 levels; deadline per SPEC 7.4 (L1 +2 days, L2 +3 working days skipping Sat/Sun/holidays using the Vietnam date, L3 manual, investor request 1 calendar day and kept on escalation); escalation history; due-date edits need a reason; overdue flags/days; only the director closes level 3
- [x] meetings with attendees, action items (global overdue view for the dashboard), change requests (approve/reject only by the director, link to a contract amendment), admin holidays
- [x] seed: the ten risks of SPEC 14.6 (probability/impact are an initial assessment, OPEN_QUESTIONS 24)
- [x] Web: `/risks` (matrix tap-to-filter, level in words + score, form with live score), `/issues` (list/table, board from lg, level and overdue chips, deadline in words, detail sheet with history, escalate, resolve, edit deadline), `/meetings` (overdue banner, actions), `/change-requests` (director decision sheet), package "Rủi ro & vướng mắc" tab
- AC check: seed risks land in the matrix cells computed from their scores (test compares the grid with the seed); overdue issues are flagged and filterable (alert generation is M7).
- Tests: api 824 (98% coverage), web 154.
- Notes: risk owner has no picker in the UI (only admins can list users); owners can be set through the API. Issue search is plain `ILIKE` (no diacritic folding) unlike documents.

## M7 – Bộ máy cảnh báo và dashboard
- [x] `alerts` + `packages.consulting_role` + `payments.due_date` + migration 0007 (up/down/up verified, `alembic check` clean)
- [x] 12 quy tắc SPEC 7.1 là hàm thuần trong `services/alert_rules.py` (100% coverage, biên ±1 ngày/điểm cho từng quy tắc); quy tắc bảo lãnh dùng lại `guarantee_rules.py`; sức khỏe gói 7.3 (`package_health`) ghi lại vào `packages.health` + lý do
- [x] engine (`alert_engine.py`): khóa chống trùng `RULE:entity:level`, tự đóng khi điều kiện hết, mở lại khi quay lại, mức tăng lên thì hết trạng thái "đã xác nhận", hoãn tối đa 7 ngày và hết hạn hoãn thì mở lại, critical không giữ được trạng thái hoãn
- [x] email: `Mailer` (SMTP/mailpit, SES, memory), critical gửi một lần (`notified_at`, gửi lỗi thì lần sau thử lại), tóm tắt 08:00 cho giám đốc và người được gán; worker chạy hằng giờ + 08:00; ghi dữ liệu xong thì chạy lại nền (gộp các lần ghi liên tiếp)
- [x] API: `/alerts` (list, get, ack, snooze, assign, refresh) và `/dashboard/summary|cashflow|top-risks|alerts|documents` (+ `timeline` đã có từ M5)
- [x] Web: `/` dashboard 8 khối (mỗi khối một endpoint, khối lỗi không làm trắng trang), `/alerts` (chip mức độ, vuốt trái xác nhận / vuốt phải hoãn có nút thay thế, hoãn kèm lý do, giao cho tôi), số cảnh báo trên thanh dưới
- AC check: seed cho `ADVANCE_GUARANTEE_SHORT` Gói 05 (critical), `GUARANTEE_MISSING` Gói 04 và 05, `CROSS_PKG_DEPENDENCY` Gói 07, Gói 03 `grey` "Chưa có hợp đồng"; chạy lại không tạo trùng; sửa dữ liệu thì cảnh báo tự đóng; dashboard 5 khối tải < 2 giây với dữ liệu seed.
- Tests: api 897 (97% coverage), web 183.
- Deviations / notes: (1) cờ nhất quán Gói 02 (7.5) vẫn nằm ở trả lời hợp đồng, không phải cảnh báo vì SPEC 7.1 không có mã tương ứng. (2) Seed còn sinh thêm `CONTRACT_ENDING`, `DOC_MISSING` đúng quy tắc, danh sách 14.7 là tập con. (3) `CROSS_PKG_DEPENDENCY`: xem OPEN_QUESTIONS 25. (4) `PAYMENT_DUE` cần `payments.due_date` (cột mới, chưa có form nhập). (5) Chưa có xuất Excel danh sách cảnh báo (M8). (6) Chạy engine mỗi giờ (SPEC 4.10) thay vì chỉ 06:00/13:00 của mục 7.

