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

### Chạy local (máy phát triển macOS)
Đã kiểm chứng 31/10/2026. Máy dùng Colima; plugin `docker compose` chưa có, nên dùng `docker run` trực tiếp.
1. Bật Docker: `colima status` (nếu chưa chạy: `colima start`). Mọi lệnh `docker` chạy với `env -u DOCKER_HOST` vì `DOCKER_HOST` có thể trỏ tới socket không tồn tại.
2. Postgres 16 (chỉ làm một lần, sau đó `docker start qlda-pg`):
   `docker run -d --name qlda-pg -e POSTGRES_USER=qlda -e POSTGRES_PASSWORD=qlda -e POSTGRES_DB=qlda -p 5432:5432 postgres:16`
   Tạo DB test: `CREATE DATABASE qlda_test;` và `CREATE EXTENSION pg_trgm; CREATE EXTENSION unaccent;` trong cả `qlda` và `qlda_test`.
3. API: `cd apps/api && uv sync`, rồi `DATABASE_URL=postgresql+asyncpg://qlda:qlda@localhost:5432/qlda .venv/bin/alembic upgrade head`.
4. Seed (admin + dòng dự án + checklist + SGD-HCM): `SEED_ADMIN_PASSWORD='<mật khẩu>' .venv/bin/python -m app.seed.run`.
5. Đồng bộ workbook gói thầu: `scripts/tracking_sync_weekly.sh` (chạy thử trước, hỏi xác nhận rồi mới ghi).
6. Chạy server: `.venv/bin/uvicorn app.main:app --port 8000` với `JWT_SECRET=<chuỗi ≥ 32 ký tự>`, `COOKIE_SECURE=false`, `STORAGE_BACKEND=memory`.
7. Web: `cd apps/web && corepack pnpm install --frozen-lockfile && corepack pnpm dev --port 5173` (Vite proxy `/api` → `localhost:8000`).
Kiểm tra: `curl http://127.0.0.1:8000/api/v1/health` → `{"status":"ok"}`; đăng nhập qua `http://127.0.0.1:5173`.

### Deploy VPS (`scripts/deploy-vps.sh`)
VPS: `deploy@103.9.78.91`, web và API phục vụ qua Caddy HTTP. Đã deploy thành công 31/10/2026 (image `20261031161302`).
1. Chạy: `env -u DOCKER_HOST PATH="$HOME/.local/bin:$PATH" bash scripts/deploy-vps.sh`. Script build API image và web, copy file, tải image lên, chạy migration, khởi động, rồi health check.
2. **Build cho `linux/amd64`** (script đã có `--platform linux/amd64`). Mac là arm64, VPS là amd64; nếu base image `python:3.12-slim` còn cache arm64 thì build lỗi. Xử lý: `docker rmi python:3.12-slim` rồi `docker pull --platform linux/amd64 python:3.12-slim`.
3. Build trên Mac chạy dưới QEMU nên lâu (khoảng 15–20 phút cho bước `uv sync`). Chờ, không hủy giữa chừng.
4. Health check đầu có thể trả 502 trong lúc API khởi động. Kiểm tra lại: `curl http://103.9.78.91/api/v1/health`.
5. Script không đồng bộ workbook. Sau deploy: copy file lên VPS (`rsync ... deploy@103.9.78.91:qlda/sync/tracking.xlsx`) rồi chạy thử:
   `ssh deploy@103.9.78.91 'cd ~/qlda && docker compose run --rm -T -v $PWD/sync:/docs:ro api python -m app.services.tracking_sync --file /docs/tracking.xlsx'`
   Chỉ thêm `--apply` sau khi đã xem báo cáo chạy thử và được xác nhận.
6. Trước khi deploy, kiểm tra trạng thái VPS chỉ đọc: `ssh deploy@103.9.78.91 'cd ~/qlda && docker compose ps'`. Deploy ghi đè thư mục `web/` của Caddy ngay ở bước "Ship files", nên nếu deploy dừng giữa chừng site có thể dùng frontend mới với API cũ. Hoàn tất hoặc chạy lại script.

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

## Quy tắc chung

### Hoàn thành công việc
- Trước khi coi là xong: build + test xanh, lint/type check đạt, tài liệu API (nếu có) đã cập nhật.
- Chỗ nào được đánh dấu "GIẢ ĐỊNH" trong tài liệu hoặc code: làm cho cấu hình được và ghi vào danh sách câu hỏi mở, không chỉ nằm trong câu trả lời.
- Không hard-code ngưỡng, giờ ca, mã lý do hay công thức nghiệp vụ: đưa vào cấu hình hoặc dữ liệu danh mục có phiên bản.
- Dữ liệu đã chốt/khóa không sửa trực tiếp; thay đổi phải đi qua quy trình điều chỉnh có ghi nhận.

### Git
- Không commit trực tiếp lên `main`. Mỗi epic/tính năng làm trên một nhánh riêng, tạo từ `main` mới nhất. Không dùng lại nhánh đã merge.
- Mỗi task hoàn thành và đã kiểm chứng: commit và push ngay. Không gom nhiều task vào một commit.
- Trước khi commit, kiểm tra `git status`. Nếu còn thay đổi chưa commit của việc khác: dừng và hỏi, không tự commit, stash hay xóa.
- `git add <tệp cụ thể>`, không dùng `git add -A`. Kiểm tra `git diff --cached`: không có bí mật, thư mục build, `node_modules/`, `.DS_Store`.
- Conventional Commits: `<type>(<scope>): <mô tả>`, với type thuộc `feat | fix | refactor | docs | test | chore | perf | ci`. Thân commit ghi ID yêu cầu liên quan và kết quả kiểm chứng.
- Không dùng `--no-verify`. Không `git push --force` trừ khi được yêu cầu rõ; không force-push nhánh đã có PR.
- Đồng bộ với `main` bằng merge, không rebase sau khi đã push.
- Không tự merge PR. Khi epic xong: mở PR vào `main` với tóm tắt, danh sách commit, kiểm chứng đã chạy (lệnh, kết quả) và chưa chạy (lý do).
- Không thêm `Co-Authored-By` trừ khi cấu hình cho phép.

### Kế hoạch và nhật ký
- Mỗi epic đang làm có một tệp plan trong `docs/plans/` (nếu có mẫu thì chép mẫu làm khung).
- Trước khi viết plan, đọc hiện trạng code. Ghi bằng chứng bằng đường dẫn file/dòng; "đã có" hay "chưa có" phải kiểm trong repo, không suy đoán.
- Trạng thái ✅ chỉ khi đã chạy kiểm chứng (test, lệnh cụ thể). Ghi rõ phần chưa chạy được và lý do.
- Sau mỗi task: cập nhật trạng thái và kết quả của task trong plan, thêm một dòng nhật ký (ngày, ID task, kết quả kiểm chứng, chỗ lệch so với kế hoạch), cùng commit với mã của task.
- Phát hiện mới trong lúc làm thì ghi vào plan, không chỉ nằm trong câu trả lời.

### Giao diện
- UI 100% tiếng Việt có dấu; ngày và số định dạng theo `vi-VN`.
- Mọi màn có đủ sáu trạng thái: đang tải, trống, lỗi, một phần, thành công, không có quyền.
- Tương phản chữ ≥ 4,5:1. Chỉ ghi "đạt" khi đã đo bằng công cụ.
- Nút chạm trên tablet ≥ 56dp.
- Chỉ ghi "đã kiểm trình duyệt" khi đã mở và đo thật trên trình duyệt. Nếu chưa, ghi "chưa kiểm" và liệt kê việc còn lại.
- Không build UI cho màn chưa được duyệt thiết kế.
