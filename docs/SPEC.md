# SPEC – Web app quản lý dự án "QLDA Cấp Xã Lâm Đồng"

> Tài liệu đặc tả để Claude Code implement. Ngôn ngữ giao diện: tiếng Việt. Tên bảng, trường, API, biến: tiếng Anh.
> Phiên bản spec: 1.0 – 06/10/2026. Nguồn nghiệp vụ: đề cương TVQLDA Gói 06, hợp đồng và quyết định các gói thầu (xem mục 14 Seed data).

---

## 0. Cách làm việc dành cho Claude Code

1. Đọc toàn bộ spec trước khi viết code. Làm theo thứ tự milestone ở mục 12. Mỗi task nhỏ một commit, thông điệp commit rõ ràng.
2. Không tự bịa dữ liệu nghiệp vụ. Số liệu seed ở mục 14 lấy từ hồ sơ thật; ô nào ghi `null` hoặc "chưa rõ" thì để trống và hiển thị "Chưa có dữ liệu".
3. Gặp chỗ mơ hồ: ghi vào `docs/OPEN_QUESTIONS.md`, chọn phương án mặc định đã nêu trong spec, tiếp tục làm, báo lại ở cuối milestone.
4. Mọi quy tắc nghiệp vụ ở mục 7 phải có unit test. Mọi API phải có test tích hợp. Không merge khi test đỏ.
5. Không đưa dữ liệu thật hay khóa bí mật vào repo. Dữ liệu seed chỉ gồm thông tin đã nêu trong spec.
6. Phạm vi MVP gồm các milestone M0–M8. Mục 13 (Phase 2, 3) chỉ là backlog để chừa chỗ gắn, chưa làm.

---

## 1. Mục tiêu và phạm vi

### 1.1 Bối cảnh
Dự án "Đầu tư trang thiết bị phục vụ hoạt động của chính quyền cấp xã và triển khai Đề án 06 trên địa bàn tỉnh Lâm Đồng" (tổng mức đầu tư 219 tỷ đồng, ngân sách tỉnh, 2026–2028) có 8 gói thầu. Nhóm Tư vấn quản lý dự án (TVQLDA, Gói 06, công ty Sài Gòn Mới) cần một công cụ chung để theo dõi tiến độ, hợp đồng, bảo lãnh, hồ sơ và rủi ro cho cả 8 gói.

### 1.2 Mục tiêu
- Một nơi duy nhất cho thông tin tổng quan dự án và từng gói thầu.
- Theo dõi tiến độ từng gói theo 5 giai đoạn của đề cương.
- Kho hồ sơ theo gói, có danh mục hồ sơ cần có và cảnh báo thiếu.
- Theo dõi hợp đồng, bảo lãnh, tạm ứng, thanh toán, và tự cảnh báo các mốc nguy cơ.
- Sổ rủi ro và sổ vướng mắc có hạn xử lý theo 3 cấp.
- Dữ liệu có nhật ký thay đổi, phục vụ quyết toán, kiểm toán, thanh tra.

### 1.3 Ngoài phạm vi MVP (xem mục 13)
Báo cáo tự động và biểu mẫu QL-01…QL-16 điền sẵn, nghiệm thu bàn giao theo từng xã, bảo hành sau bàn giao, OCR và AI, thông báo Zalo, giao diện riêng cho Chủ đầu tư (trong MVP chỉ có vai trò chỉ xem).

### 1.4 Người dùng và vai trò
| Mã vai trò | Tên | Mô tả |
|---|---|---|
| `admin` | Quản trị hệ thống | Quản lý người dùng, cấu hình, xem nhật ký |
| `director` | Giám đốc QLDA | Toàn quyền nghiệp vụ, duyệt (đóng) rủi ro, vướng mắc cấp 3 |
| `procurement` | Chuyên gia đấu thầu – hợp đồng | Gói thầu, hợp đồng, bảo lãnh, hồ sơ lựa chọn nhà thầu |
| `technical` | Chuyên gia kỹ thuật | Tiến độ, chất lượng, nghiệm thu, hồ sơ kỹ thuật |
| `cost` | Chuyên gia chi phí, thanh quyết toán | Tạm ứng, thanh toán, giải ngân, hồ sơ thanh toán |
| `onsite` | Cán bộ thường trực | Nhật ký hằng ngày, vướng mắc, tải hồ sơ |
| `clerk` | Văn thư, lưu trữ | Quản lý hồ sơ, đánh số văn bản |
| `viewer` | Chỉ xem (Chủ đầu tư, TVGS khi được cấp) | Xem dashboard, gói thầu, tiến độ; không thấy hồ sơ nhạy cảm |

Ma trận quyền chi tiết ở mục 8.

---

## 2. Kiến trúc kỹ thuật

### 2.1 Stack (bắt buộc)
- **Frontend:** React 18 + Vite + TypeScript, React Router, TanStack Query, React Hook Form + Zod, Tailwind CSS + shadcn/ui, Recharts (biểu đồ), gantt tự dựng bằng SVG hoặc thư viện `gantt-task-react`, dayjs.
- **Backend:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x (async) + Alembic, Uvicorn/Gunicorn, APScheduler (job định kỳ), boto3, argon2-cffi, python-jose (JWT).
- **Cơ sở dữ liệu:** PostgreSQL 16, extension `pg_trgm`, `unaccent`.
- **Lưu file:** Amazon S3 (MinIO khi chạy local), upload qua presigned URL.
- **Triển khai:** AWS. Frontend: S3 + CloudFront. Backend: ECS Fargate (2 service: `api`, `worker`). DB: RDS PostgreSQL. Email: SES. Bí mật: Secrets Manager. IaC: Terraform. Local: Docker Compose.
- **Chất lượng:** pytest + httpx, Playwright (e2e), ESLint, Ruff, mypy, pre-commit, GitHub Actions.

### 2.2 Cấu trúc repo (monorepo)
```
qlda-capxa/
  apps/
    web/                 # React + Vite
    api/                 # FastAPI
      app/
        main.py
        core/            # config, security, db, logging
        models/          # SQLAlchemy models
        schemas/         # Pydantic schemas
        routers/         # 1 file / resource
        services/        # nghiệp vụ (alerts, finance, checklist, search)
        jobs/            # APScheduler jobs (worker)
        seed/            # seed data (JSON + script)
      alembic/
      tests/
  infra/terraform/
  docker-compose.yml
  docs/ (SPEC.md, OPEN_QUESTIONS.md, ADR/)
  .github/workflows/
```

### 2.3 Quy ước chung
- Múi giờ lưu UTC, hiển thị `Asia/Ho_Chi_Minh`. Ngày hiển thị `dd/MM/yyyy`. Tiền tệ VND, hiển thị phân cách nghìn bằng dấu chấm (ví dụ `51.505.400.000`), lưu `NUMERIC(18,0)`.
- Mọi bảng có `id` (UUID v7 hoặc UUID v4), `created_at`, `updated_at`, `created_by`, `updated_by`. Xóa mềm bằng `deleted_at` cho bảng nghiệp vụ.
- API: REST, prefix `/api/v1`, JSON, phân trang `?page=&page_size=` (mặc định 20, tối đa 100), sắp xếp `?sort=field,-field`, lọc theo tên trường. Lỗi trả `{ "error": { "code", "message", "details" } }`.
- Xác thực: JWT access token 15 phút + refresh token 7 ngày (cookie `HttpOnly`, `Secure`, `SameSite=Lax`). Mật khẩu băm argon2. Bắt buộc đổi mật khẩu lần đầu.
- Mọi thay đổi dữ liệu nghiệp vụ ghi `audit_log` (xem 4.18).
- Tìm kiếm tiếng Việt không dấu: dùng `unaccent` + `pg_trgm`.

---

## 3. Mô hình dữ liệu

Kiểu: `uuid`, `text`, `int`, `numeric`, `date`, `timestamptz`, `bool`, `jsonb`. Cột `*_id` là khóa ngoại. Enum lưu dạng `text` kèm `CHECK`.

### 3.1 `users`
`id, email (unique), full_name, phone, role (enum mục 1.4), is_active, password_hash, must_change_password, last_login_at`.

### 3.2 `projects`
`id, code, name, investor_org_id, decision_maker (text), total_investment numeric, funding_source, start_year, end_year, location, treasury_account, project_code_kbnn (text, ví dụ 8200685), description`.

### 3.3 `organizations`
`id, name, short_name, tax_code, address, representative, position, phone, email, bank_account, bank_name, org_type` với `org_type` ∈ `investor | consultant | contractor | supervisor | auditor | beneficiary | bank | other`.

### 3.4 `packages` (gói thầu)
`id, project_id, number (1..8, unique trong dự án), name, scope_summary, package_type (goods | consulting), package_price numeric, selection_form (open_tender | direct_appointment_short), selection_method (one_stage_one_envelope | one_stage_two_envelope | short_procedure), approved_duration_days int, etbmt_no, kh_lcnt_decision (text), approval_decision (text, QĐ phê duyệt kết quả LCNT), winning_price numeric null, winning_org_text (text), current_stage (enum mục 3.6), status, progress_pct numeric(5,2), health (green | amber | red, tính tự động), notes`.
`status` ∈ `planning | bidding | negotiating | contract_signed | executing | accepted | settled | cancelled`.

### 3.5 `contracts`
`id, package_id, contract_no, signed_date, effective_date, duration_days, planned_end_date, extended_end_date null, end_date_override bool, contract_type (lump_sum | unit_price), value numeric, advance_pct numeric, advance_amount numeric, advance_recovery_note, performance_bond_pct numeric, performance_bond_amount numeric, warranty_bond_pct numeric, warranty_bond_amount numeric, penalty_rate_pct numeric, penalty_unit (day | week), penalty_cap_pct numeric, payment_terms_text, payment_term_days int, copies_text, investor_signer, investor_account, status (draft | signed | executing | accepted | liquidated | terminated), source_doc_id null, data_quality_note`.
Hợp đồng sửa đổi dùng bảng `contract_amendments` (xem 3.9).

### 3.6 Giai đoạn chuẩn (enum `stage_code`)
`S1_START` Khởi động, `S2_SELECTION` Lựa chọn nhà thầu, `S3_EXECUTION` Thực hiện hợp đồng, `S4_ACCEPTANCE` Nghiệm thu bàn giao, `S5_PAYMENT_SETTLEMENT` Thanh toán, thanh lý, quyết toán.

### 3.7 `contract_parties` (liên danh)
`id, contract_id, organization_id, role (lead | member | sole), share_pct, share_amount, advance_amount, bank_account, bank_name, notes`.

### 3.8 `contract_items` (hàng hóa, dịch vụ trong hợp đồng)
`id, contract_id, member_org_id null, line_no, name, unit, quantity numeric, unit_price numeric, amount numeric, warranty_months int, requires_calibration bool, origin, notes`.

### 3.9 `contract_amendments`
`id, contract_id, amendment_no, signed_date, type (duration | value | scope | other), description, new_value numeric null, new_end_date date null, document_id null`.

### 3.10 `guarantees` (bảo lãnh)
`id, contract_id, provider_org_id (thành viên nộp), guarantee_type (bid | performance | advance | warranty), bank_name, guarantee_no, amount numeric, issue_date, effective_from date, expiry_date date null, validity_text (ví dụ "đến khi nghiệm thu"), status (pending | valid | expiring | expired | released | missing), required bool, document_id null, verified bool, verify_note`.
`status` do hệ thống tính từ `expiry_date` (xem 7.2). `verified=false` dùng cho số liệu chưa đối chiếu bản gốc (OCR).

### 3.11 `payments`
`id, contract_id, organization_id null, payment_type (advance | payment | recovery | penalty), seq int, amount numeric, requested_date null, paid_date null, status (planned | requested | approved | paid | rejected), invoice_no, treasury_ref, document_id null, notes`.

### 3.12 `disbursement_plan`
`id, project_id, package_id null, year int, month int, planned_amount numeric, actual_amount numeric null`. Dùng cho đường kế hoạch giải ngân.

### 3.13 `stage_plans` (kế hoạch và thực tế theo giai đoạn của từng gói)
`id, package_id, stage_code, name, planned_start, planned_end, actual_start, actual_end, progress_pct numeric(5,2), weight numeric(5,2), status (not_started | in_progress | done | delayed | blocked), notes`.
Khi tạo gói, hệ thống sinh sẵn 5 giai đoạn (mục 3.6) với `weight` mặc định 10/20/40/20/10 (có thể sửa).

### 3.14 `tasks` (đầu việc chi tiết trong giai đoạn)
`id, package_id, stage_plan_id, title, assignee_id, planned_start, planned_end, actual_end, status (todo | doing | done | blocked), priority (low | normal | high), weight, notes`.

### 3.15 `progress_logs` (nhật ký hằng ngày)
`id, package_id, log_date, progress_pct numeric(5,2), summary text, issues text, next_steps text, author_id, attachments (jsonb danh sách document_id)`. Duy nhất `(package_id, log_date, author_id)`.

### 3.16 `risks`
`id, code (R-001…), project_id, package_id null, title, description, category (schedule | cost | quality | legal | contract | supply | safety | other), probability int 1..5, impact int 1..5, score (= probability × impact, tính tự động), owner_id, mitigation text, contingency text, status (open | mitigating | occurred | closed), due_date null, source (de_cuong | analysis | manual), last_reviewed_at`.

### 3.17 `issues` (vướng mắc, yêu cầu của Chủ đầu tư)
`id, code (V-001…), package_id null, issue_type (operational | contract | schedule | investor_request | other), level int (1|2|3), title, description, reported_by, assigned_to, reported_at, due_at, status (open | in_progress | escalated | resolved | closed), resolution text, decided_by (text), decision_doc_id null, resolved_at`.
`due_at` tự tính (mục 7.4).

### 3.18 `documents`
`id, project_id, package_id null, contract_id null, category (legal | selection | contract | execution | acceptance | payment | other), doc_type (mã mục 4.6), title, doc_no, doc_date, issuer, confidentiality (normal | sensitive), file_key, file_name, mime_type, size_bytes, sha256, version int, parent_document_id null (bản trước), is_current bool, text_content text null, text_extracted bool, search_vector tsvector, tags text[], uploaded_by, notes`.
Chỉ mục: GIN trên `search_vector`, GIN `pg_trgm` trên `title`, unique `(package_id, sha256)` để chặn trùng.

### 3.19 `checklist_templates` và `checklist_items`
- `checklist_templates`: `id, package_type, stage_code, doc_type, title, required bool, due_offset_days int, condition text null`.
- `checklist_items` (sinh theo từng gói): `id, package_id, template_id, stage_code, doc_type, title, required, status (missing | received | not_applicable), document_id null, due_date null, note`.

### 3.20 `meetings` và `action_items` (MVP chỉ cần ghi nhận cơ bản)
- `meetings`: `id, project_id, package_id null, meeting_type (kickoff | package_kickoff | weekly | issue_resolution | other), meeting_date, location, chair, attendees (jsonb), minutes text, document_id null`.
- `action_items`: `id, meeting_id null, package_id null, title, owner_id, due_date, status (open | done | cancelled)`.

### 3.21 `change_requests`
`id, package_id, code, change_type (model | origin | allocation | schedule | other), description, proposed_by_org_id, supervisor_opinion text, tvqlda_opinion text, status (proposed | reviewing | approved | rejected | appendix_signed), decided_at, document_id null`.

### 3.22 `alerts`
`id, alert_type (mục 7.1), severity (info | warning | critical), entity_type, entity_id, package_id null, title, message, due_date null, status (open | acknowledged | resolved | suppressed), assigned_to null, fingerprint (unique chống trùng), first_seen_at, resolved_at, acknowledged_by`.

### 3.23 `outgoing_doc_numbers`
`id, year, doc_kind (CV | BC | TB | BB | QD ...), seq int, doc_no (ví dụ `012/CV-QLDA-SGM`), subject, issued_date, created_by`. Unique `(year, doc_kind, seq)`. Dùng khi tạo số văn bản đi (mục 4.15).

### 3.24 `audit_log`
`id, ts, user_id, action (create | update | delete | login | download | export), entity_type, entity_id, changes jsonb (diff trước/sau), ip, user_agent`.

---

## 4. Đặc tả tính năng

Mỗi tính năng có: mô tả, màn hình, quy tắc, tiêu chí nghiệm thu (AC).

### 4.1 Đăng nhập, người dùng, phân quyền
- Màn hình: `/login`, `/profile`, `/admin/users`.
- Đăng nhập bằng email và mật khẩu. Khóa tạm 15 phút sau 5 lần sai liên tiếp. Đổi mật khẩu lần đầu.
- Admin tạo, sửa, khóa người dùng, gán vai trò. Không xóa người dùng đã có dữ liệu, chỉ khóa.
- **AC:** gọi API không có quyền trả 403; vai trò `viewer` không thấy tài liệu `sensitive`; mọi lần đăng nhập ghi audit.

### 4.2 Dashboard tổng quan (`/`)
Các khối, mỗi khối là một component độc lập có API riêng `/api/v1/dashboard/*`:
1. **Thẻ dự án:** tên, chủ đầu tư, tổng mức đầu tư, nguồn vốn, thời gian, số gói, ngày hợp đồng Gói 06 còn lại (đếm ngược đến `planned_end_date`).
2. **Dải 8 gói thầu:** mỗi gói một thẻ gồm số, tên rút gọn, nhà thầu, giá trúng, giai đoạn hiện tại, thanh tiến độ, nhãn `health` (xanh, vàng, đỏ). Bấm vào mở chi tiết gói.
3. **Chỉ số tài chính:** tổng giá gói thầu, tổng giá trúng, tổng giá trị hợp đồng đã ký, tổng tạm ứng, tổng đã thanh toán, tỷ lệ giải ngân so với kế hoạch vốn; biểu đồ cột kế hoạch và thực tế theo tháng.
4. **Mốc sắp tới (30 ngày):** hạn hợp đồng, hạn bảo lãnh, hạn giai đoạn, hạn vướng mắc, hạn báo cáo, sắp theo ngày.
5. **Cảnh báo đang mở:** đếm theo mức độ, danh sách 10 cảnh báo nghiêm trọng nhất, bấm để mở thực thể liên quan.
6. **Rủi ro hàng đầu:** 5 rủi ro điểm cao nhất, ma trận nhiệt 5×5.
7. **Hồ sơ thiếu:** số hạng mục checklist còn thiếu theo gói.
8. **Đường găng đơn giản:** biểu đồ thời gian chung các gói và các hợp đồng (Gói 06, Gói 07, các gói cung cấp), đánh dấu ngày hôm nay và các vạch hết hạn.
- **AC:** dashboard tải dưới 2 giây với dữ liệu seed; số trên thẻ khớp với dữ liệu chi tiết; mọi thẻ đều mở được trang nguồn.

### 4.3 Quản lý gói thầu (`/packages`, `/packages/:id`)
- Danh sách: bảng và thẻ, lọc theo trạng thái, giai đoạn, `health`, nhà thầu; tìm theo tên.
- Chi tiết gói gồm các tab:
  1. **Tổng quan:** thông tin cơ bản (mục 3.4), giá gói so với giá trúng (hiển thị chênh lệch và % tiết kiệm), nhà thầu, liên danh, các văn bản pháp lý liên quan.
  2. **Hợp đồng:** thông tin hợp đồng (3.5), bảng liên danh (3.7), bảng hàng hóa (3.8), phụ lục sửa đổi (3.9), kết quả kiểm tra dữ liệu hợp đồng (mục 7.5).
  3. **Bảo lãnh và thanh toán:** xem 4.5.
  4. **Tiến độ:** xem 4.4.
  5. **Hồ sơ:** xem 4.6.
  6. **Rủi ro, vướng mắc:** các rủi ro và vướng mắc gắn với gói.
  7. **Nhật ký:** nhật ký hằng ngày và lịch sử thay đổi của gói.
- Quy tắc: không xóa gói đã có hợp đồng; đổi `status` ghi audit; `health` tính theo 7.3.
- **AC:** tạo, sửa, xem đủ trường; nhập liên danh phải thỏa tổng `share_pct` = 100 và tổng `share_amount` = `contract.value`.

### 4.4 Theo dõi tiến độ
- **Giai đoạn:** mỗi gói có 5 giai đoạn (3.13), nhập ngày kế hoạch, ngày thực tế, % hoàn thành; hệ thống tính `progress_pct` của gói = tổng(`progress_pct` × `weight`) / tổng(`weight`).
- **Đầu việc:** CRUD `tasks` trong giai đoạn; kéo thả đổi trạng thái (bảng Kanban todo, doing, done, blocked); khi tất cả đầu việc `done` đề xuất đánh dấu giai đoạn `done` (người dùng xác nhận).
- **Gantt:** `/progress` hiển thị toàn bộ giai đoạn của 8 gói trên một trục thời gian; thanh kế hoạch và thanh thực tế; vạch hôm nay; vạch hết hạn hợp đồng; phóng to theo tuần, tháng.
- **Nhật ký hằng ngày:** form nhập nhanh trên điện thoại (ngày, % tiến độ, tóm tắt, vướng mắc, việc tiếp theo, đính kèm ảnh); danh sách theo gói; cảnh báo nếu chưa có nhật ký sau 17:00 trong ngày làm việc đối với gói đang `executing` (7.1).
- **Bảng theo dõi lựa chọn nhà thầu (tương đương QL-06):** bảng 8 gói với các cột: QĐ phê duyệt HSMT, đăng TBMT, đóng mở thầu, số nhà thầu, hoàn thành đánh giá, QĐ phê duyệt KQLCNT, ký hợp đồng, tình trạng, vướng mắc; ô trễ so với kế hoạch tô đỏ. Xuất Excel.
- **AC:** đổi ngày giai đoạn cập nhật Gantt ngay; `health` đổi đúng theo quy tắc; xuất QL-06 ra `.xlsx` mở được trong Excel.

### 4.5 Hợp đồng, bảo lãnh, tạm ứng, thanh toán
- **Bảo lãnh:** CRUD, đính kèm file hồ sơ, cờ `verified`. Màn hình lịch bảo lãnh `/finance/guarantees` sắp theo `expiry_date`, màu theo mức độ còn lại (quá hạn, còn 3 ngày, còn 10 ngày).
- **Tạm ứng và thanh toán:** CRUD `payments`; tính **số dư tạm ứng chưa thu hồi** = tổng `advance` − tổng `recovery` theo hợp đồng và theo từng thành viên liên danh.
- **Bảng theo dõi hợp đồng (tương đương QL-07):** mỗi hợp đồng một dòng: nhà thầu, số và ngày, giá trị, hạn hợp đồng, bảo lãnh thực hiện (giá trị, hạn), tạm ứng (giá trị, bảo lãnh, hạn), thanh toán lũy kế, tạm ứng đã thu hồi. Dòng tổng cộng. Xuất Excel.
- **Kế hoạch giải ngân:** nhập kế hoạch theo tháng cho từng gói; so sánh với thực tế tính từ `payments` đã `paid`.
- **Gói 06 (hợp đồng của TVQLDA):** hiển thị lịch thanh toán 3 đợt (tạm ứng 30%, lần 1 90% thu hồi tạm ứng, lần 2 10%) và điều kiện từng đợt (lần 1 khi Gói 03, 04, 05, 07 nghiệm thu 100%; lần 2 khi quyết toán được phê duyệt). Điều kiện hiển thị trạng thái đạt hoặc chưa đạt tự động dựa trên `status` các gói.
- **AC:** số dư tạm ứng khớp tay; tổng giá trị hợp đồng khớp với các hàng hóa; xuất QL-07 đúng cột.

### 4.6 Quản lý hồ sơ
- **Cấu trúc:** theo 6 nhóm `category`: pháp lý dự án, lựa chọn nhà thầu, hợp đồng, thực hiện hợp đồng, nghiệm thu bàn giao, thanh toán quyết toán. Mỗi tài liệu thuộc một gói (hoặc cấp dự án nếu `package_id` null).
- **Mã `doc_type` chuẩn:** `decision_invest`, `decision_estimate`, `decision_kh_lcnt`, `etbmt`, `etbmt_approval`, `bid_opening_minutes`, `evaluation_report`, `appraisal_report`, `decision_selection_result`, `acceptance_letter`, `contract`, `contract_completion_minutes`, `guarantee_performance`, `guarantee_advance`, `guarantee_warranty`, `delivery_plan`, `delivery_notice`, `coc_cq`, `calibration_cert`, `site_inspection_minutes` (QL-08), `acceptance_minutes` (QL-09), `handover_minutes` (QL-10), `supervisor_report`, `value_statement` (QL-11), `invoice`, `liquidation_minutes` (QL-15), `settlement_checklist` (QL-16), `meeting_minutes` (QL-04), `proposal_letter` (QL-05), `report_weekly`, `report_monthly`, `report_final`, `report_adhoc`, `photo`, `other`.
- **Tải lên:** kéo thả nhiều file; file lớn upload trực tiếp lên S3 bằng presigned URL (tối đa 200 MB/file); tính `sha256` ở client hoặc sau khi upload; chặn trùng trong cùng gói; sau upload, form yêu cầu nhập tối thiểu: loại, tiêu đề, số, ngày, nhóm.
- **Phiên bản:** tải lên bản mới của cùng tài liệu tạo `version+1`, bản cũ `is_current=false` và vẫn xem được. Có so sánh lịch sử (danh sách phiên bản).
- **Xem trước:** PDF, ảnh xem trực tiếp (presigned GET, hết hạn 5 phút); Word, Excel tải về.
- **Tìm kiếm:** ô tìm kiếm toàn cục (`/api/v1/search?q=`) trên tiêu đề, số văn bản, ghi chú, và `text_content` (không dấu). Worker trích xuất text từ PDF có text (`pdftotext`), `.docx` (`python-docx`), đánh dấu `text_extracted`. PDF scan để `text_extracted=false` (OCR để Phase 3).
- **Checklist hồ sơ:** mỗi gói có danh mục hồ sơ cần có (mục 4.7). Gán tài liệu vào hạng mục; hạng mục `required` chưa có sau `due_date` sinh cảnh báo. Tỷ lệ hoàn thành hồ sơ hiển thị trên thẻ gói.
- **Nhạy cảm:** tài liệu `confidentiality=sensitive` (ví dụ hồ sơ Gói 05, thông tin Công an) chỉ vai trò `admin`, `director`, `procurement`, `technical` thấy; mọi lượt tải ghi audit.
- **AC:** tải lên, xem, tải về, tạo phiên bản, tìm kiếm không dấu "bao lanh tam ung" ra tài liệu "Bảo lãnh tạm ứng"; vai trò `viewer` không thấy tài liệu nhạy cảm.

### 4.7 Danh mục hồ sơ chuẩn (seed cho `checklist_templates`)
**Gói hàng hóa (`goods`):**
- S2: QĐ phê duyệt E-HSMT; E-TBMT; biên bản mở thầu; báo cáo đánh giá E-HSDT; báo cáo thẩm định KQLCNT; QĐ phê duyệt KQLCNT; thư chấp thuận E-HSDT và trao hợp đồng.
- S2→S3: hợp đồng; biên bản hoàn thiện hợp đồng; bảo lãnh thực hiện hợp đồng (hạn: ngày hiệu lực + 7); bảo lãnh tạm ứng (trước khi tạm ứng); Mẫu 02.a (tạm ứng).
- S3: kế hoạch giao hàng chi tiết; thông báo lịch giao hàng; biên bản họp khởi động gói (QL-04); biên bản kiểm tra hiện trường (QL-08); CO, CQ, chứng nhận bảo hành, kiểm định/hiệu chuẩn (nếu có).
- S4: báo cáo kết quả giám sát của TVGS; biên bản vận hành thử; biên bản nghiệm thu (QL-09); biên bản bàn giao cho đơn vị thụ hưởng (QL-10).
- S5: bảng xác định giá trị khối lượng (QL-11); hóa đơn; bảo lãnh bảo hành; biên bản thanh lý (QL-15); danh mục hồ sơ quyết toán (QL-16).

**Gói tư vấn (`consulting`):** QĐ phê duyệt KQLCNT; hợp đồng và biên bản hoàn thiện; sản phẩm bàn giao theo hợp đồng; biên bản nghiệm thu; bảng xác định khối lượng (QL-11); hóa đơn; biên bản thanh lý (QL-15).

### 4.8 Sổ rủi ro (`/risks`)
- CRUD, lọc theo gói, trạng thái, danh mục, chủ sở hữu.
- `score = probability × impact`; nhãn: 1–5 thấp, 6–12 trung bình, 13–25 cao.
- Ma trận nhiệt 5×5 bấm để lọc.
- Quy tắc: rủi ro `open` quá 14 ngày không có `last_reviewed_at` sinh cảnh báo nhắc rà soát; chỉ `director` được đóng (`closed`).
- Nhập sẵn các rủi ro từ đề cương và phát hiện phân tích (mục 14.6).
- **AC:** điểm tự tính; ma trận đúng số lượng; lịch sử thay đổi trong audit.

### 4.9 Sổ vướng mắc (`/issues`)
- Phân 3 cấp theo đề cương:
  - Cấp 1: tác nghiệp (lịch giao hàng, phối hợp đơn vị thụ hưởng, bổ sung hồ sơ). TVQLDA tự xử lý, hạn 2 ngày.
  - Cấp 2: điều khoản hợp đồng, thay đổi kỹ thuật tương đương, điều chỉnh phân bổ. TVQLDA tham mưu, Chủ đầu tư quyết định, hạn 3 ngày làm việc.
  - Cấp 3: chậm nghiêm trọng, vi phạm hợp đồng, điều chỉnh tiến độ làm kéo dài dự án. Chủ đầu tư quyết định hoặc báo cấp có thẩm quyền; hạn theo quy định (người dùng nhập).
- Loại `investor_request`: yêu cầu bằng văn bản của Chủ đầu tư về chậm tiến độ, nhân sự, báo cáo. **Hạn khắc phục cố định 1 ngày** (kể cả thứ bảy, chủ nhật).
- Nút "Nâng cấp lên cấp cao hơn" ghi lại lịch sử; có trường quyết định của Chủ đầu tư và tệp đính kèm.
- **AC:** `due_at` tính đúng theo cấp; quá hạn sinh cảnh báo; lịch sử nâng cấp đủ.

### 4.10 Cảnh báo (`/alerts`)
- Hệ thống sinh cảnh báo tự động bằng job hằng giờ (mục 7.1), chống trùng bằng `fingerprint`.
- Người dùng có thể xác nhận (`acknowledged`), gán người xử lý, tạm tắt (`suppressed`) kèm lý do và hạn.
- Cảnh báo tự đóng (`resolved`) khi điều kiện không còn đúng.
- Gửi email tóm tắt hằng ngày 08:00 giờ Việt Nam cho người được gán và `director` (qua SES); cảnh báo `critical` gửi ngay.
- **AC:** tạo dữ liệu tình huống thì cảnh báo xuất hiện trong vòng 1 giờ; sửa dữ liệu thì tự đóng; không trùng.

### 4.11 Họp và đầu việc (MVP tối thiểu)
Ghi biên bản họp (loại, ngày, thành phần, nội dung, file đính kèm) và tạo danh sách việc cần làm có người phụ trách, hạn. Hiển thị việc quá hạn ở dashboard.

### 4.12 Thay đổi, điều chỉnh
Ghi nhận đề xuất thay đổi (model, xuất xứ, phân bổ, tiến độ), ý kiến TVGS, ý kiến TVQLDA, quyết định của Chủ đầu tư, phụ lục. Liên kết với `contract_amendments` nếu có.

### 4.13 Nhập, xuất dữ liệu
- Xuất Excel: QL-06 (4.4), QL-07 (4.5), danh sách rủi ro, vướng mắc, cảnh báo, danh mục hồ sơ.
- Nhập Excel (khung): nhập danh sách hàng hóa hợp đồng và bảng phân bổ theo xã (chuẩn bị cho Phase 2).
- **AC:** mọi file xuất mở được bằng Excel, tiêu đề tiếng Việt, định dạng ngày và tiền đúng.

### 4.14 Quản trị
`/admin/users`, `/admin/audit` (lọc theo người, thực thể, thời gian), `/admin/settings` (ngưỡng cảnh báo, ngày nghỉ lễ, danh mục `doc_type`, mẫu checklist).

### 4.15 Đánh số văn bản đi (nhỏ)
Màn hình tạo số văn bản theo quy tắc `[Số]/[Loại]-QLDA-SGM` (ví dụ `012/CV-QLDA-SGM`), số tăng dần theo từng loại và năm, không trùng. Nhập trích yếu, ngày.

### 4.16 Tìm kiếm toàn cục
Ô tìm kiếm trên thanh trên cùng: tìm trong gói thầu, tài liệu, rủi ro, vướng mắc, hợp đồng; kết quả nhóm theo loại, có đoạn trích.

### 4.17 Phi chức năng
- Hiệu năng: danh sách dưới 500 ms với 10.000 bản ghi; upload file 100 MB không làm nghẽn API (presigned URL).
- Bảo mật: OWASP Top 10, kiểm tra quyền ở tầng service, giới hạn kích thước và MIME, quét virus (điểm gắn, chưa bắt buộc), CORS giới hạn, `Content-Security-Policy`, nhật ký truy cập tài liệu nhạy cảm.
- Sao lưu: RDS tự động 7 ngày; S3 bật versioning; kiểm tra khôi phục hằng quý.
- Khả dụng: giao diện dùng được trên điện thoại (nhật ký hằng ngày, xem trạng thái, tải ảnh); trên máy tính cho phần còn lại. Hỗ trợ bàn phím và độ tương phản đạt WCAG AA cho các màn hình chính.

### 4.18 Audit log
Middleware ghi `audit_log` cho mọi `POST/PUT/PATCH/DELETE` trên bảng nghiệp vụ, lưu diff trước và sau (che các trường nhạy cảm như `password_hash`). Tải tài liệu nhạy cảm và xuất dữ liệu cũng ghi.

---

## 5. API (REST `/api/v1`)

Mọi endpoint yêu cầu JWT trừ `/auth/login`, `/auth/refresh`, `/health`. Danh sách trả `{items, total, page, page_size}`. Lỗi trả `{error:{code,message,details}}`. Quyền xem mục 8.

| Nhóm | Endpoint | Ghi chú |
|---|---|---|
| Auth | `POST /auth/login`, `/auth/refresh`, `/auth/logout`, `GET /auth/me`, `POST /auth/change-password` | |
| Users | `GET/POST /users`, `GET/PATCH /users/{id}`, `POST /users/{id}/reset-password` | admin |
| Project | `GET/PATCH /project` | dự án đang chọn (header `X-Project-Id`); nhiều dự án: xem mục 16 |
| Dashboard | `GET /dashboard/summary`, `/dashboard/timeline`, `/dashboard/cashflow`, `/dashboard/top-risks`, `/dashboard/alerts` | |
| Packages | `GET /packages`, `GET/PATCH /packages/{id}`, `GET /packages/{id}/overview` | |
| Contracts | `GET/POST /packages/{id}/contracts`, `GET/PATCH /contracts/{id}`, `/contracts/{id}/parties`, `/items`, `/amendments` | CRUD con |
| Guarantees | `GET/POST /contracts/{id}/guarantees`, `PATCH/DELETE /guarantees/{id}` | |
| Payments | `GET/POST /contracts/{id}/payments`, `PATCH /payments/{id}`, `POST /payments/{id}/mark-paid` | |
| Disbursement | `GET/PUT /project/disbursement-plan` | |
| Stages | `GET /packages/{id}/stages`, `PATCH /stage-plans/{id}` | |
| Tasks | `GET/POST /packages/{id}/tasks`, `PATCH/DELETE /tasks/{id}` | hỗ trợ `depends_on` |
| Progress logs | `GET/POST /packages/{id}/progress-logs`, `PATCH /progress-logs/{id}` | 1 bản ghi/gói/ngày |
| Risks | `GET/POST /risks`, `GET/PATCH /risks/{id}`, `GET /risks/matrix` | lọc theo gói, mức |
| Issues | `GET/POST /issues`, `GET/PATCH /issues/{id}`, `POST /issues/{id}/escalate`, `/resolve` | |
| Documents | `GET /documents` (lọc, tìm kiếm), `POST /documents/upload-url`, `POST /documents` (xác nhận sau upload), `GET /documents/{id}`, `POST /documents/{id}/versions`, `GET /documents/{id}/download-url`, `PATCH/DELETE /documents/{id}` | presigned URL |
| Checklists | `GET /packages/{id}/checklist`, `PATCH /checklist-items/{id}`, `POST /packages/{id}/checklist/instantiate` | |
| Meetings | `GET/POST /meetings`, `PATCH /meetings/{id}`, `/meetings/{id}/action-items` | |
| Change requests | `GET/POST /change-requests`, `PATCH /change-requests/{id}`, `POST /change-requests/{id}/decide` | |
| Alerts | `GET /alerts`, `POST /alerts/{id}/ack`, `POST /alerts/{id}/snooze` | |
| Doc numbers | `POST /outgoing-doc-numbers`, `GET /outgoing-doc-numbers` | |
| Search | `GET /search?q=` | |
| Import/Export | `GET /export/{resource}.xlsx`, `POST /import/{resource}` (dry-run + commit) | |
| Audit | `GET /audit-log` | admin, director |
| Admin | `GET/POST /admin/checklist-templates`, `/admin/doc-types`, `/admin/alert-rules` | |

Mỗi endpoint ghi có test hợp đồng (pytest) kiểm tra: 200/201 đúng, 403 đúng vai trò, 422 dữ liệu sai.

---

## 6. Màn hình và route frontend

> Nguyên tắc giao diện: **mobile-first**. Mọi màn hình bên dưới phải thiết kế và làm cho điện thoại trước (360 px), sau đó mở rộng lên máy tính bảng và máy tính. Quy cách chi tiết ở **mục 15**; nếu mâu thuẫn với mô tả bố cục ở mục 6 và 4, mục 15 được ưu tiên.

| Route | Màn hình | Vai trò chính |
|---|---|---|
| `/login` | Đăng nhập | tất cả |
| `/` | Tổng quan dự án (dashboard, mục 4.2) | tất cả |
| `/packages` | Danh sách 8 gói: thẻ + bảng, lọc trạng thái, sức khỏe | tất cả |
| `/packages/:id` | Chi tiết gói, 7 tab: Tổng quan, Hợp đồng, Tiến độ, Hồ sơ, Rủi ro & vướng mắc, Thanh toán, Nhật ký | tất cả |
| `/progress` | Gantt toàn dự án + đường phụ thuộc giữa gói | PM, kỹ thuật |
| `/daily-log` | Nhập nhật ký hằng ngày (tối ưu điện thoại) | hiện trường |
| `/contracts` | Hợp đồng và bảo lãnh (bảng hết hạn gần nhất đứng đầu) | PM, chi phí |
| `/payments` | Lịch thanh toán và giải ngân | chi phí |
| `/documents` | Kho tài liệu, tìm kiếm, lọc loại/gói/giai đoạn | tất cả |
| `/risks` | Sổ rủi ro + ma trận 5×5 | PM |
| `/issues` | Vướng mắc 3 cấp, kanban và bảng | PM |
| `/meetings` | Họp và biên bản, action items | PM |
| `/change-requests` | Yêu cầu thay đổi | PM, kỹ thuật |
| `/alerts` | Trung tâm cảnh báo | tất cả |
| `/outgoing-docs` | Số văn bản đi | văn thư |
| `/admin/*` | Người dùng, mẫu checklist, loại tài liệu, quy tắc cảnh báo, audit | admin |

Chung: sidebar thu gọn, breadcrumb, ô tìm kiếm toàn cục (Ctrl+K), chế độ sáng/tối, tiếng Việt toàn bộ, định dạng tiền `1.234.567 đ`, ngày `dd/MM/yyyy`. Mọi bảng có sắp xếp, lọc, phân trang, xuất Excel. Trạng thái rỗng, đang tải và lỗi có thiết kế.

---

## 7. Quy tắc nghiệp vụ và bộ máy cảnh báo

Cài trong `app/services/rules.py` và `app/jobs/alerts.py` (APScheduler, chạy 06:00 và 13:00 giờ Việt Nam, và sau mỗi thay đổi liên quan). Mỗi quy tắc có test đơn vị với dữ liệu biên.

### 7.1 Cảnh báo

| Mã | Điều kiện | Mức |
|---|---|---|
| `GUARANTEE_EXPIRING` | Bảo lãnh còn ≤10 ngày hết hạn: warning; ≤3 ngày hoặc đã hết hạn: critical | warning/critical |
| `ADVANCE_GUARANTEE_SHORT` | Còn dư nợ tạm ứng và ngày hết hạn bảo lãnh tạm ứng < ngày kết thúc hợp đồng + số ngày thanh toán (mặc định 7) | critical |
| `GUARANTEE_MISSING` | Bảo đảm thực hiện HĐ chưa có sau hiệu lực + 7 ngày; hoặc có tạm ứng nhưng chưa có bảo lãnh tạm ứng | critical |
| `CONTRACT_ENDING` | Còn ≤14 ngày kết thúc hợp đồng và tiến độ <100% | warning, ≤5 ngày critical |
| `STAGE_DELAYED` | Giai đoạn quá ngày kế hoạch kết thúc mà chưa hoàn thành | warning |
| `PROGRESS_BEHIND` | Tiến độ thực tế thấp hơn kế hoạch >10 điểm % | warning, >25 critical |
| `ISSUE_SLA` | Vướng mắc quá `due_at` (7.4) | warning, quá 1 ngày critical |
| `DOC_MISSING` | Mục bắt buộc của checklist chưa có tài liệu khi giai đoạn đã vào giai đoạn tương ứng | warning |
| `DAILY_LOG_MISSING` | Gói đang thực hiện chưa có nhật ký ngày làm việc sau 17:00 | info |
| `REPORT_DUE` | Báo cáo tuần (thứ Sáu), tháng (ngày 25), quý đến hạn | info |
| `CROSS_PKG_DEPENDENCY` | Hợp đồng TVGS kết thúc trước gói cung cấp cuối cùng; hoặc TVQLDA kết thúc trước nghiệm thu dự kiến | warning |
| `PAYMENT_DUE` | Đợt thanh toán đến hạn trong ≤5 ngày mà chưa đủ điều kiện | warning |

Cảnh báo có khóa chống trùng (`rule_code + entity_id + level`); tự đóng khi điều kiện hết; có thể tạm hoãn (snooze) tối đa 7 ngày; critical không snooze được.

### 7.2 Trạng thái bảo lãnh
`valid` (hết hạn sau >10 ngày), `expiring` (≤10 ngày), `expired`, `released` (đã hoàn trả), `missing` (kỳ vọng có nhưng chưa nhập).

### 7.3 Sức khỏe gói thầu
`red` nếu có cảnh báo critical đang mở hoặc tiến độ chậm >25 điểm; `amber` nếu có warning hoặc chậm >10 điểm; còn lại `green`; `grey` cho gói chưa bắt đầu hoặc đã đóng. Hiển thị lý do khi rê chuột.

### 7.4 Hạn xử lý vướng mắc
L1: ngày tạo + 2 ngày; L2: ngày chuyển cấp + 3 ngày làm việc (bỏ T7, CN, danh sách ngày lễ cấu hình); L3: theo quy định, nhập tay. Yêu cầu của chủ đầu tư: 1 ngày. Có thể sửa tay `due_at` kèm lý do.

### 7.5 Kiểm tra nhất quán dữ liệu hợp đồng
Chạy khi lưu hợp đồng và hiển thị cờ "Cần kiểm tra":
1. `contract.value` bằng giá trúng thầu của gói.
2. Thời gian thực hiện bằng thời gian trong KHLCNT.
3. Tài khoản chủ đầu tư trùng tài khoản kho bạc của dự án.
4. Tổng `share_amount` các thành viên liên danh bằng giá trị hợp đồng.
5. Tổng tạm ứng của các thành viên bằng `advance_amount`.
6. `advance_amount` bằng `advance_pct × value` (sai số 1 đồng).
7. Giá trị bảo lãnh bằng `pct × value`.
8. Cờ giá cố định/điều chỉnh được khớp loại hợp đồng; hợp đồng trọn gói không được ghi điều chỉnh giá.
9. Ngày kết thúc kế hoạch = ngày bắt đầu + thời gian − 1; nếu khác thì cảnh báo nhưng vẫn cho ghi đè.

---

## 8. Ma trận phân quyền

R = xem, W = tạo/sửa, A = duyệt/đóng, – = không.

| Tài nguyên | admin | director | procurement | technical | cost | onsite | clerk | viewer |
|---|---|---|---|---|---|---|---|---|
| Dự án, người dùng | W | R | R | R | R | – | – | R |
| Gói thầu | W | W | W | R | R | R | R | R |
| Hợp đồng, bảo lãnh | W | A | W | R | W | R | R | R |
| Thanh toán, giải ngân | W | A | R | R | W | – | – | R |
| Tiến độ, nhiệt ký | W | W | R | W | R | W | – | R |
| Rủi ro, vướng mắc | W | A | W | W | W | W | – | R |
| Tài liệu thường | W | W | W | W | W | W | W | R |
| Tài liệu nhạy cảm (Gói 05, Công an) | W | W | chỉ gói được giao | chỉ gói được giao | – | – | – | – |
| Họp, thay đổi | W | A | W | W | R | R | R | R |
| Số văn bản đi | W | R | R | R | R | – | W | R |
| Audit log | R | R | – | – | – | – | – | – |

Cờ `is_sensitive` trên tài liệu/gói: chỉ người dùng trong `package_access` mới thấy, ngoài ra danh sách chỉ hiện "tài liệu hạn chế". Kiểm tra ở tầng service, không chỉ ở route.

---

## 9. Lưu trữ tệp, tìm kiếm và trích văn bản

- Bucket S3 riêng, chặn truy cập công khai, mã hóa SSE-S3, versioning. Khóa: `projects/{pid}/packages/{pkg}/{doc_id}/v{n}/{filename}`.
- Upload: client xin `upload-url` (hết hạn 10 phút, giới hạn 100 MB, MIME cho phép: pdf, docx, xlsx, doc, xls, jpg, png, zip), tải thẳng lên S3, rồi gọi `POST /documents` kèm checksum SHA-256; trùng checksum cùng gói thì cảnh báo.
- Tải xuống: `download-url` hết hạn 5 phút, ghi audit nếu tài liệu nhạy cảm.
- Worker nền trích văn bản: PDF có lớp chữ (pdftotext), docx (python-docx), xlsx (openpyxl); PDF ảnh quét để trạng thái `needs_ocr` (điểm gắn OCR/AI về sau, chưa làm). Văn bản đưa vào `tsvector` với `unaccent` và `pg_trgm`.
- Tên file lưu gốc, hiển thị theo `doc_type` + số + ngày; chuẩn hóa tên không dấu khi tạo khóa S3.

---

## 10. Hạ tầng, môi trường và biến cấu hình

### 10.1 Local (Docker Compose)
Dịch vụ: `db` (postgres:16), `minio`, `api` (uvicorn reload), `worker`, `web` (vite dev), `mailpit`. `make up`, `make seed`, `make test`, `make lint`. File `.env.example` đầy đủ, không có bí mật thật.

### 10.2 AWS (Terraform trong `infra/terraform`)
VPC 2 AZ; S3 + CloudFront cho web; ECS Fargate hai service (`api`, `worker`) sau ALB HTTPS (ACM); RDS PostgreSQL 16 Multi-AZ tắt ở môi trường dev; S3 tài liệu; SES gửi mail; Secrets Manager; CloudWatch logs và cảnh báo; IAM quyền tối thiểu. Hai workspace: `dev`, `prod`. Triển khai qua GitHub Actions với OIDC, không lưu khóa dài hạn.

### 10.3 Biến môi trường chính
`DATABASE_URL`, `JWT_SECRET`, `JWT_ACCESS_MINUTES=15`, `JWT_REFRESH_DAYS=7`, `S3_BUCKET`, `S3_ENDPOINT_URL` (MinIO), `AWS_REGION`, `SES_SENDER`, `CORS_ORIGINS`, `APP_TIMEZONE=Asia/Ho_Chi_Minh`, `ALERT_RUN_HOURS=6,13`, `AI_PROVIDER=none`.

---

## 11. Kiểm thử và CI

- Backend: pytest + httpx; mỗi quy tắc mục 7 có ít nhất 3 ca (đủ, biên, vi phạm); test phân quyền cho từng cặp vai trò × tài nguyên nhạy cảm; coverage ≥ 80% cho `services/`.
- Frontend: Vitest cho hàm tính toán; Playwright cho 5 luồng: đăng nhập, tạo hợp đồng + bảo lãnh và thấy cảnh báo, upload tài liệu, nhập nhật ký, đóng vướng mắc.
- CI GitHub Actions: ruff, mypy, pytest, eslint, tsc, vitest, build; chặn merge nếu lỗi. Pre-commit cho định dạng.
- Dữ liệu seed chạy được trong CI để kiểm tra cảnh báo mong đợi (mục 14.7).

---

## 12. Lộ trình triển khai (milestone)

Mỗi milestone kết thúc khi đạt Definition of Done: test xanh, migration chạy được từ DB trống, README cập nhật, không còn TODO chặn, demo chạy với dữ liệu seed.

**M0 – Khung dự án.** Monorepo, Docker Compose, FastAPI hello + `/health`, Vite + Tailwind + shadcn, CI, Alembic, lint. AC: `make up` chạy cả hệ thống; CI xanh.

**M1 – Xác thực và phân quyền.** Bảng users, login/refresh, argon2, RBAC dependency, audit middleware, màn hình đăng nhập, quản lý người dùng. AC: ma trận mục 8 có test; khóa tạm sau 5 lần sai.

**M2 – Dự án, gói thầu, hợp đồng.** Mô hình mục 3.1–3.9, seed 8 gói, màn hình danh sách và chi tiết gói (tab Tổng quan, Hợp đồng), kiểm tra nhất quán 7.5. AC: seed hiện đủ 8 gói, cờ nhất quán xuất hiện đúng ở Gói 02 và Gói 04.

**M3 – Bảo lãnh và thanh toán.** Mục 3.10–3.12, màn hình hợp đồng/bảo lãnh/thanh toán, trạng thái 7.2, kế hoạch giải ngân. AC: bảo lãnh TPBank/BIDV Gói 05 hiện `expiring` và `ADVANCE_GUARANTEE_SHORT`.

**M4 – Kho tài liệu.** S3/MinIO presigned, phân loại, phiên bản, trích văn bản, tìm kiếm, tài liệu nhạy cảm, checklist theo gói. AC: upload 50 MB thành công, tìm có dấu/không dấu, người không có quyền không thấy tài liệu nhạy cảm.

**M5 – Tiến độ.** Giai đoạn, công việc, Gantt, nhật ký hằng ngày (mobile), xuất QL-06. AC: Gantt kéo đổi ngày được, ngày kết thúc theo quy tắc cộng−1 và ghi đè được.

**M6 – Rủi ro và vướng mắc.** Sổ rủi ro, ma trận 5×5, vướng mắc 3 cấp, SLA 7.4, họp, yêu cầu thay đổi. AC: rủi ro seed hiển thị đúng ô ma trận; quá hạn tạo cảnh báo.

**M7 – Bộ máy cảnh báo và dashboard.** Toàn bộ 7.1, email SES/mailpit, dashboard mục 4.2, sức khỏe gói 7.3. AC: bộ seed cho đúng danh sách cảnh báo ở 14.7.

**M8 – Hoàn thiện MVP.** Tìm kiếm toàn cục, import/export Excel, số văn bản đi, audit viewer, Terraform dev, tài liệu vận hành. AC: triển khai lên AWS dev, Playwright 5 luồng xanh.

Công việc giao diện mobile-first theo từng milestone nằm ở mục 15.11. Sau M8: mục 13.

---

## 13. Backlog giai đoạn 2–3 (chưa làm trong MVP)

1. Biểu mẫu QL-01…QL-16: sinh file Word/PDF từ dữ liệu, ký số (điểm gắn).
2. Nghiệm thu từng xã: danh sách xã, thiết bị theo xã, biên bản, ảnh hiện trường, mã QR thiết bị.
3. Bảo hành: phiếu yêu cầu, SLA xử lý, thống kê.
4. OCR và AI: OCR tiếng Việt cho bản scan, tóm tắt hợp đồng, hỏi đáp trên tài liệu, phát hiện sai khác. Hook sẵn `AI_PROVIDER`.
5. Thông báo Zalo/SMS.
6. Cổng xem cho chủ đầu tư (chỉ đọc, báo cáo định kỳ).
7. Ứng dụng di động cài được (PWA, ngoại tuyến cho nhật ký).
8. Báo cáo tuần/tháng/quý tự động theo mẫu.

---

## 14. Dữ liệu khởi tạo (seed)

Chỉ dùng dữ liệu đã có trong tài liệu; chỗ chưa biết để `NULL` và tạo mục trong `docs/OPEN_QUESTIONS.md`. Số tiền VND, kiểu số nguyên. Mục đánh dấu [OCR] cần đối chiếu bản gốc.

### 14.1 Dự án
Dự án thiết bị cấp xã/Đề án 06 Lâm Đồng, chủ đầu tư Sở KH&CN Lâm Đồng, tổng mức 219 tỷ đồng, tài khoản kho bạc 9552.2.8200685; QĐ 2824, 3255, 220, 239 (KHLCNT).

### 14.2 Gói thầu (8 gói)
| Gói | Giá gói thầu | Giá trúng | Ghi chú |
|---|---|---|---|
| 01 | 237.382.337 | 237.382.337 | An Lập Thịnh |
| 02 | 270.141.231 | theo HĐ 54 | Trường Thịnh NT |
| 03 | 117.472.203.146 | NULL | E-TBMT IB2600424701; Viettel E-HSDT 101.886.000.000; BĐDT 3.524.166.000; chưa có hợp đồng |
| 04 | 62.298.200.000 | 51.505.400.000 | liên danh Nguyên Luân 60% / TTB Mẫu Giáo Ti Ti 40% |
| 05 | 14.946.900.000 | 13.599.975.000 | liên danh P&N 9.386.475.000 / BSN 4.213.500.000 |
| 06 | 1.820.685.517 | 1.726.920.000 | TVQLDA, Sài Gòn Mới |
| 07 | 509.634.139 | NULL | chưa có giá trị hợp đồng |
| 08 | 720.713.320 | NULL | chưa có giá trị hợp đồng |

### 14.3 Hợp đồng
HĐ 53 (Gói 01, 20/7/2026, 60 ngày); HĐ 54 (Gói 02); HĐ 71 (Gói 04, 14/9/2026); HĐ 72 (Gói 05, 14/9/2026); HĐ 80 (Gói 06, 24/9/2026, 120 ngày đến 22/01/2027, tạm ứng 518.076.000, thanh toán 1.554.228.000 và 172.692.000, phạt 1%/ngày tối đa 8%); HĐ 73, 74 (Gói 07, 08, giá trị NULL). Ngày kết thúc tính start + thời gian − 1, kèm cờ nếu văn bản ghi khác (Gói 01/02 ghi 18/9 so với 17/9; Gói 04 ghi 13/11 so với 12/11).

### 14.4 Bảo lãnh
- Gói 04 bảo đảm thực hiện: ABBank, 1.545.162.000, phát hành 12/9/2026 (bản scan [OCR] từng đọc là 1.515.162.000; đúng là 1.545.162.000 = 3% × giá trị).
- Gói 05 tạm ứng: TPBank 2.815.942.500 phát hành 15/9/2026, hết hạn 13/11/2026 [OCR]; BIDV 1.264.050.000, hết hạn ≤13/11/2026 [OCR]. Hợp đồng kết thúc 12/11/2026 → cảnh báo `ADVANCE_GUARANTEE_SHORT`.
- Thiếu: Gói 04 bảo lãnh tạm ứng (15.451.620.000); Gói 05 bảo đảm thực hiện (407.999.250). Tạo bản ghi `missing`.

### 14.5 Thanh toán
Gói 06: tạm ứng 518.076.000, đợt 1 1.554.228.000, đợt 2 172.692.000. Gói 04: tạm ứng 15.451.620.000 và đợt còn lại 20.602.160.000 theo hợp đồng. Các gói khác để trống, nhập sau.

### 14.6 Rủi ro khởi tạo
Lấy từ đề cương và phát hiện: (1) Gói 03 chậm hợp đồng – nút thắt cung cấp thiết bị; (2) bảo lãnh tạm ứng Gói 05 hết hạn trước/sát hạn hợp đồng; (3) thiếu bảo lãnh Gói 04 và Gói 05; (4) Gói 02 có điều khoản hợp đồng sai khác (thiết kế thi công, điều chỉnh giá vs trọn gói, 90 vs 60 ngày, tài khoản 9552.2.8171939 khác 8200685, phạt 10%/tuần tối đa 20%, nhắc GIS); (5) Gói 01/02 có thể phải gia hạn; (6) Gói 04 giá thấp hơn 17,3% so với giá gói thầu → rủi ro chất lượng; (7) thời gian kiểm định/hiệu chuẩn; (8) chia thanh toán liên danh; (9) hợp đồng TVGS (~13/12/2026) kết thúc trước gói cung cấp; (10) chậm bàn giao mặt bằng/điện/mạng tại xã. Mỗi rủi ro có xác suất, tác động, chủ trì, biện pháp, hạn; điểm do hệ thống tính.

### 14.7 Cảnh báo kỳ vọng sau seed (dùng cho test M7)
`ADVANCE_GUARANTEE_SHORT` Gói 05 (critical); `GUARANTEE_MISSING` Gói 04 (tạm ứng) và Gói 05 (thực hiện); cờ nhất quán Gói 02; `CROSS_PKG_DEPENDENCY` khi TVGS kết thúc trước gói cung cấp; Gói 03 hiện `grey` kèm lý do "chưa có hợp đồng".

### 14.8 Checklist chuẩn
Seed mẫu checklist cho gói hàng hóa và gói tư vấn theo mục 4.7 (E-HSMT, QĐ KQLCNT, hợp đồng, bảo đảm thực hiện, bảo lãnh tạm ứng, tiến độ chi tiết, kiểm định, nghiệm thu, thanh lý, bảo hành...).

---

---

## 15. Giao diện frontend: mobile-first

Mục này bổ sung và ưu tiên hơn mô tả bố cục ở mục 4 và 6. Người dùng thường xem tiến độ, nhập nhật ký, chụp ảnh và duyệt cảnh báo ngay tại hiện trường bằng điện thoại, nên điện thoại là thiết bị chính, máy tính dùng cho phần nhập liệu nặng (Gantt, bảng lớn, nhập hợp đồng).

### 15.1 Nguyên tắc
1. Viết CSS từ nhỏ đến lớn: kiểu mặc định là điện thoại, dùng tiền tố `sm:`, `md:`, `lg:`, `xl:` của Tailwind để mở rộng, không viết ngược bằng `max-width`.
2. Thiết kế thử ở 360×640 trước; mọi màn hình dùng được từ 320 px chiều rộng, không có cuộn ngang ở cấp trang.
3. Một tác vụ chính cho mỗi màn hình điện thoại; thao tác chính nằm trong tầm ngón cái (nửa dưới màn hình).
4. Không dựa vào hover: mọi thông tin hiện khi rê chuột (ví dụ lý do sức khỏe gói) phải có tương đương khi chạm.
5. Hiệu năng trên mạng 4G yếu: tải chậm theo route (code splitting), ảnh nén, danh sách phân trang hoặc cuộn vô hạn, hiển thị khung chờ (skeleton).

### 15.2 Điểm ngắt và lưới
| Tên | Rộng | Thiết bị | Bố cục |
|---|---|---|---|
| mặc định | 0–639 px | điện thoại | một cột, thanh điều hướng dưới |
| `sm` | ≥640 px | điện thoại ngang | một cột rộng, lưới 2 cột cho thẻ |
| `md` | ≥768 px | máy tính bảng | thanh bên thu gọn (chỉ biểu tượng), lưới 2–3 cột |
| `lg` | ≥1024 px | máy tính | thanh bên đầy đủ, bảng đầy đủ cột, chia 2 khung (danh sách + chi tiết) |
| `xl` | ≥1280 px | màn hình lớn | nội dung tối đa 1440 px, căn giữa |

Khoảng cách theo bội số 4 px; lề trang 16 px ở điện thoại, 24 px từ `md`.

### 15.3 Điều hướng
- **Điện thoại:** thanh điều hướng dưới cố định, 5 mục: Tổng quan, Gói thầu, Nhật ký (nút giữa nổi bật), Cảnh báo (kèm số chưa đọc), Thêm. Mục "Thêm" mở ngăn kéo từ dưới lên với Hợp đồng, Thanh toán, Tài liệu, Rủi ro, Vướng mắc, Họp, Thay đổi, Văn bản đi, Quản trị, Tài khoản.
- Thanh trên cùng gọn: tiêu đề màn hình, nút quay lại, nút tìm kiếm (mở màn hình tìm kiếm toàn màn hình), tên người dùng/ảnh đại diện. Thanh trên ẩn khi cuộn xuống và hiện khi cuộn lên.
- **Máy tính bảng:** thanh bên thu gọn bên trái. **Máy tính:** thanh bên đầy đủ có nhóm menu, Ctrl+K mở tìm kiếm.
- Nhớ vị trí cuộn và bộ lọc khi quay lại từ trang chi tiết.
- Tab trong chi tiết gói: cuộn ngang, tab đang chọn tự cuộn vào giữa; giữ tab theo URL (`?tab=progress`) để liên kết chia sẻ được.

### 15.4 Quy tắc thành phần
**Mục tiêu chạm:** tối thiểu 44×44 px, khoảng cách giữa các mục chạm ≥ 8 px. Nút chính rộng toàn chiều ngang ở điện thoại.

**Bảng dữ liệu → thẻ.** Dưới `md`, mọi bảng chuyển thành danh sách thẻ: dòng 1 tên/mã, dòng 2 trạng thái (nhãn màu), 2–3 trường quan trọng nhất, nút "…" cho thao tác. Từ `md` hiện bảng thật với cột cố định đầu tiên, ẩn bớt cột phụ qua nút "Cột". Dùng một thành phần `ResponsiveList` nhận định nghĩa cột và hàm vẽ thẻ để khỏi viết hai lần.

**Biểu mẫu.** Một cột; nhãn trên ô nhập; kiểu bàn phím đúng (`inputmode="numeric"` cho số tiền, `type="date"` bản địa, `tel`, `email`); ô tiền tự phân nhóm nghìn khi nhập; nút Lưu dính ở đáy màn hình; báo lỗi ngay dưới ô; giữ bản nháp khi mất mạng hoặc khi thoát nhầm. Biểu mẫu dài chia bước (stepper) hoặc phần có thể gập.

**Bộ lọc.** Dưới `md`: nút "Lọc" mở ngăn kéo dưới, hiện số bộ lọc đang bật, chip bộ lọc đang áp dụng nằm trên danh sách và gỡ được bằng một chạm. Từ `md`: thanh lọc nội tuyến.

**Hộp thoại.** Điện thoại dùng ngăn kéo dưới (bottom sheet) có thể vuốt xuống để đóng, thay cho hộp thoại giữa màn hình; từ `md` dùng hộp thoại thường. Xác nhận thao tác phá hủy luôn có bước xác nhận riêng.

**Thẻ chỉ số (KPI).** Lưới 2 cột ở điện thoại, 4 cột ở `lg`. Mỗi thẻ: nhãn, giá trị lớn, so sánh/xu hướng nhỏ, chạm để đi tới danh sách đã lọc.

**Biểu đồ.** Chiều cao co giãn theo khung, chú giải bên dưới, nhãn trục thưa dần ở màn hình nhỏ, chạm để xem giá trị (không hover). Mỗi biểu đồ có bản bảng số liệu thay thế cho trình đọc màn hình.

**Gantt.** Điện thoại không vẽ Gantt kéo thả; hiển thị **dòng thời gian dạng danh sách** (mỗi giai đoạn một thẻ có thanh tiến độ mini, ngày bắt đầu–kết thúc, nhãn chậm/đúng hạn) và chế độ xem Gantt chỉ đọc có thể cuộn ngang với ghim cột tên. Kéo thả chỉnh ngày chỉ bật từ `lg`; ở điện thoại sửa ngày qua biểu mẫu.

**Trạng thái và màu.** Mọi trạng thái có nhãn chữ và biểu tượng, không dùng màu đơn thuần (xanh/vàng/đỏ/xám kèm "Đúng hạn", "Cần chú ý", "Nguy cấp", "Chưa bắt đầu"). Đạt độ tương phản WCAG AA ở cả chế độ sáng và tối.

### 15.5 Màn hình ưu tiên cho điện thoại

**a) Tổng quan (`/`).** Từ trên xuống: lời chào + ngày; dải "Cần xử lý hôm nay" (tối đa 3 cảnh báo critical, chạm để mở); lưới KPI 2×2 (tiến độ chung, số gói đúng hạn/chậm, bảo lãnh sắp hết hạn, vướng mắc quá hạn); danh sách 8 gói dạng thẻ nhỏ có chấm sức khỏe; biểu đồ giải ngân (có thể gập); rủi ro hàng đầu. Kéo xuống để làm mới.

**b) Danh sách gói (`/packages`).** Thẻ mỗi gói: số gói, tên rút gọn, nhà thầu, giá trị, thanh tiến độ, chấm sức khỏe, ngày kết thúc và số ngày còn lại. Ô tìm kiếm cố định trên cùng, chip lọc theo giai đoạn và sức khỏe.

**c) Chi tiết gói (`/packages/:id`).** Đầu trang cố định gọn (số gói, tên, sức khỏe, tiến độ %). Tab cuộn ngang. Tab Tổng quan dùng các phần gập (accordion): Thông tin chung, Hợp đồng, Bảo lãnh, Thanh toán, Cảnh báo của gói. Hành động nhanh (nút nổi): "Thêm nhật ký", "Tải tài liệu", "Báo vướng mắc".

**d) Nhật ký hằng ngày (`/daily-log`) — màn hình quan trọng nhất cho hiện trường.** Mở được trong 2 chạm từ thanh dưới. Chọn gói (nhớ gói gần nhất), ngày mặc định hôm nay, % hoàn thành bằng thanh trượt + ô số, công việc đã làm, vướng mắc, nhân lực (số người), thời tiết, ảnh (chụp trực tiếp từ camera, tối đa 10 ảnh, nén phía máy khách xuống ≤ 1600 px cạnh dài). Lưu nháp tự động; gửi được khi mất mạng (xem 15.7). Một nút "Gửi" dính đáy.

**e) Cảnh báo (`/alerts`).** Danh sách thẻ theo mức (critical trước), vuốt trái để xác nhận, vuốt phải để hoãn (nếu cho phép), chạm để mở thực thể liên quan. Số chưa đọc trên thanh dưới.

**f) Tài liệu (`/documents`).** Danh sách thẻ với biểu tượng loại file, tên chuẩn hóa, gói, loại, ngày, dung lượng. Nút nổi "Tải lên": chọn tệp hoặc chụp ảnh tài liệu (nhiều trang gộp thành một PDF phía máy khách, tùy chọn). Xem trước PDF/ảnh trong khung toàn màn hình có nút tải về/chia sẻ.

**g) Vướng mắc (`/issues`) và Rủi ro (`/risks`).** Thẻ có nhãn cấp (L1/L2/L3) và hạn xử lý còn lại. Tạo nhanh bằng biểu mẫu tối giản (tiêu đề, gói, mức, ảnh), điền chi tiết sau. Ma trận 5×5 ở điện thoại hiển thị dạng lưới thu nhỏ, chạm vào ô để lọc danh sách bên dưới.

**h) Hợp đồng/bảo lãnh/thanh toán.** Chủ yếu để xem trên điện thoại (thẻ + chi tiết gập); nhập liệu hợp đồng ưu tiên màn hình lớn nhưng vẫn phải dùng được trên điện thoại. Bảo lãnh sắp hết hạn có đếm ngược và nhãn màu ở đầu danh sách.

**i) Từ màn hình `lg` trở lên.** Bố cục chia hai khung (danh sách bên trái, chi tiết bên phải), bảng đầy đủ, Gantt kéo thả, thao tác hàng loạt, nhập/xuất Excel, phím tắt.

### 15.6 PWA
- Manifest đầy đủ (tên "QLDA Cấp xã", biểu tượng 192/512 và maskable, `display: standalone`, màu chủ đề, `lang: vi`) để cài lên màn hình chính.
- Service worker (Workbox) bọc app shell, tệp tĩnh và các yêu cầu GET danh mục; chiến lược: app shell cache-first, API đọc stale-while-revalidate, API ghi không cache.
- Nhắc "Cài ứng dụng" một lần, tắt được; thông báo "Có phiên bản mới, tải lại" khi cập nhật.
- Thông báo đẩy (Web Push) là backlog (mục 13), nhưng cấu trúc service worker phải chừa chỗ.

### 15.7 Ngoại tuyến và mạng yếu
Phạm vi MVP: **chỉ nhật ký hằng ngày và tải ảnh** hoạt động ngoại tuyến.
- Lưu bản nháp và hàng đợi gửi trong IndexedDB (thư viện `idb`); mỗi mục có `client_id` (UUID) làm khóa chống trùng, API chấp nhận `Idempotency-Key`.
- Khi có mạng, đồng bộ nền theo thứ tự; hiển thị nhãn trạng thái từng mục: "Chưa gửi", "Đang gửi", "Đã gửi", "Lỗi – thử lại".
- Ảnh tải lên bằng presigned URL có thể tiếp tục khi gián đoạn (thử lại tối đa 5 lần, giãn cách tăng dần).
- Banner "Đang ngoại tuyến" nhỏ ở đầu trang; các màn hình khác hiển thị dữ liệu đã cache gần nhất có nhãn "Cập nhật lúc …" và vô hiệu hóa nút ghi không hỗ trợ ngoại tuyến kèm giải thích.
- Xung đột: nhật ký đã tồn tại cho cùng gói + ngày thì hỏi người dùng gộp hay ghi đè.

### 15.8 Hệ thống thiết kế
- Tailwind + shadcn/ui; token màu, cỡ chữ, bo góc, bóng định nghĩa bằng biến CSS (`:root` và `.dark`) trong `apps/web/src/styles/tokens.css`.
- Chữ: Inter (hỗ trợ tiếng Việt đầy đủ), cỡ gốc 16 px (không dưới 14 px cho nội dung), chiều cao dòng 1.5; tiêu đề `text-xl` ở điện thoại, `text-2xl` từ `md`.
- Màu ngữ nghĩa: `success`, `warning`, `danger`, `info`, `neutral`; chế độ sáng/tối theo hệ điều hành và có công tắc thủ công.
- Biểu tượng: lucide-react, kích thước 20 px, luôn có nhãn đọc màn hình (`aria-label`).
- Chuyển động ngắn (≤ 200 ms), tôn trọng `prefers-reduced-motion`.
- Thư viện thành phần dùng chung đặt trong `apps/web/src/components/ui` và `components/responsive` (`ResponsiveList`, `BottomNav`, `BottomSheet`, `FilterSheet`, `StatCard`, `StatusBadge`, `MoneyInput`, `PhotoCapture`, `HealthDot`, `EmptyState`). Tài liệu bằng Storybook hoặc trang `/dev/components` (chỉ bật ở môi trường dev) có xem thử ở 360, 768 và 1280 px.

### 15.9 Khả năng tiếp cận và địa phương hóa
- WCAG 2.1 AA; điều hướng bàn phím đầy đủ trên máy tính, thứ tự focus hợp lý, hiện vòng focus rõ; hỗ trợ đọc màn hình cho thẻ, bảng, biểu đồ; cỡ chữ theo thiết lập hệ điều hành không làm vỡ bố cục (kiểm tra ở 200%).
- Toàn bộ giao diện tiếng Việt, chuỗi tách vào tệp ngôn ngữ (`i18next`, mặc định `vi`) để dễ thêm tiếng Anh sau.
- Định dạng: tiền `1.234.567 đ` (số lớn ở thẻ KPI rút gọn "1,73 tỷ"), ngày `dd/MM/yyyy`, giờ 24 giờ, múi giờ Asia/Ho_Chi_Minh.

### 15.10 Tiêu chí hiệu năng frontend
- Lighthouse (hồ sơ mobile, mạng Slow 4G): Performance ≥ 85, Accessibility ≥ 95, PWA đạt, cho `/`, `/packages`, `/daily-log`.
- LCP ≤ 2,5 s, CLS ≤ 0,1, INP ≤ 200 ms trên thiết bị tầm trung.
- JS ban đầu ≤ 200 KB nén gzip; thư viện nặng (Gantt, biểu đồ, trình xem PDF) tải theo yêu cầu.
- Danh sách trên 100 mục dùng ảo hóa (virtualization) hoặc phân trang.

### 15.11 Công việc triển khai (bổ sung vào lộ trình mục 12)
- **M0:** cấu hình Tailwind điểm ngắt mục 15.2, token mục 15.8, bố cục khung `AppShell` (BottomNav / Sidebar), bộ ba trình duyệt mobile/tablet/desktop trong Playwright.
- **M1:** màn hình đăng nhập và quản lý người dùng đã mobile-first; chuỗi ngôn ngữ `vi`.
- **M2–M3:** `ResponsiveList`, `StatusBadge`, `MoneyInput`, `BottomSheet`; danh sách gói, chi tiết gói, hợp đồng/bảo lãnh/thanh toán dạng thẻ ↔ bảng.
- **M4:** `PhotoCapture`, chụp tài liệu, tải lên nhiều tệp, xem trước toàn màn hình.
- **M5:** dòng thời gian dạng danh sách (điện thoại), Gantt kéo thả (từ `lg`), màn hình nhật ký hằng ngày, PWA + hàng đợi ngoại tuyến (15.6–15.7).
- **M6–M7:** vướng mắc/rủi ro/cảnh báo với vuốt thao tác; dashboard mobile-first.
- **M8:** kiểm tra Lighthouse, kiểm tra thủ công trên thiết bị thật (một iPhone, một Android tầm trung), sửa lỗi tiếp cận.

**Tiêu chí hoàn thành bổ sung (Definition of Done cho mọi màn hình):** (1) đã kiểm tra ở 360, 768, 1280 px, không có cuộn ngang trang; (2) mục tiêu chạm ≥ 44 px; (3) dùng được không cần hover; (4) có trạng thái tải, rỗng, lỗi; (5) kiểm tra tương phản và nhãn đọc màn hình; (6) ảnh chụp màn hình ở ba cỡ đính vào PR.

### 15.12 Kiểm thử giao diện
Playwright chạy ba dự án: `mobile` (Pixel 5, 393×851), `tablet` (iPad Mini), `desktop` (1280×800). Các luồng mục 11 chạy ở cả ba. Thêm: kiểm tra không tràn ngang (`document.scrollingElement.scrollWidth <= innerWidth`), kiểm tra axe-core không có lỗi mức nghiêm trọng, và một ca ngoại tuyến (tắt mạng, tạo nhật ký, bật mạng, thấy "Đã gửi").

---

## 16. Nhiều dự án cùng lúc

Ứng dụng quản lý nhiều dự án; dự án cấp xã Lâm Đồng ở các mục trên là một dự án loại `procurement`. Mục này bổ sung và ưu tiên hơn các câu "một dự án duy nhất ở MVP".

### 16.1 Mô hình
- `projects.project_type`: `procurement` (gói thầu, hợp đồng, bảo lãnh, thanh toán) hoặc `software_delivery` (lịch WBS, báo cáo tuần, tồn đọng chờ CĐT). Loại quyết định danh sách module (`app/core/project_types.py`) mà menu hiển thị.
- `project_members(project_id, user_id, role)`: vai trò theo dự án (cùng 8 vai trò mục 1.4). `users.role` chỉ còn là vai trò mặc định khi thêm người vào dự án; riêng `admin` là quản trị hệ thống, thấy mọi dự án và không cần ghế.
- `project_id` có thêm ở `issues`, `change_requests`, `alerts`, `audit_log` (null cho đăng nhập và tài khoản), `outgoing_doc_numbers`. Mã `R-001`, `V-001`, `C-001` và số văn bản đi duy nhất **trong dự án**.

### 16.2 API
- Mọi request nghiệp vụ gửi header `X-Project-Id`. Thiếu header: dùng dự án duy nhất của người dùng; có nhiều dự án thì `400`. Không thuộc dự án thì `403`; admin hệ thống thì qua.
- `require(resource, level)` kiểm vai trò **trong dự án của request**. Thực thể truy cập theo id (gói, hợp đồng, tài liệu, rủi ro, vướng mắc, họp…) thuộc dự án khác trả `404`.
- `GET /projects` (dự án của tôi, kèm vai trò và module), `POST /projects` (admin), `GET /projects/{id}/members`, `PUT|DELETE /projects/{id}/members/{user_id}` (admin). Tạo người dùng mới tự thêm vào dự án admin đang chọn.
- Engine cảnh báo chạy từng dự án; email do giám đốc **của dự án đó** nhận.

### 16.3 Dự án `software_delivery`
- Bảng `wbs_tasks` (giai đoạn, đầu việc, mốc; kế hoạch gốc + tiến độ thực tế), `weekly_reports` (kỳ 7 ngày thứ Sáu–thứ Năm tính từ ngày bắt đầu kế hoạch), `decision_items` (tồn đọng chờ CĐT). Rủi ro dùng lại bảng `risks` (thêm `group_name`, `owner_text`, `note`); 4 mức Rất cao/Cao/Trung bình/Thấp ↔ điểm xác suất × tác động 25/16/9/4.
- API `/delivery/*`: `tasks`, `overview`, `weeks`, `reports/{week_start}`, `decisions`. Tỷ trọng mọi con số % là số ngày làm việc của đầu việc; mốc không có trọng số. Quy tắc trạng thái ở `services/delivery_rules.py`.
- Cảnh báo: `TASK_LATE`, `MILESTONE_SOON`, `WEEKLY_REPORT_MISSING`, `DECISION_OVERDUE`, `RISK_VERY_HIGH`.
- Frontend: trang chủ, Gantt, báo cáo tuần, rủi ro, tồn đọng; quyền dùng các tài nguyên `wbs`, `weekly_report`, `decision` (ma trận ở `app/core/rbac.py`).
- Dự án SGD-HCM được seed từ kế hoạch gốc (`app/seed/sgd_hcm_plan.py`, 11 giai đoạn, 35 đầu việc + 9 mốc); chưa có ai trong dự án ngoài admin hệ thống.

---

## Phụ lục: câu hỏi mở (ghi vào `docs/OPEN_QUESTIONS.md`)
1. Hợp đồng và giá trúng Gói 03; giá trị HĐ 73, 74 (Gói 07, 08).
2. Bản gốc bảo lãnh Gói 05 để xác nhận ngày hết hạn.
3. Gói 04 bảo lãnh tạm ứng và Gói 05 bảo đảm thực hiện đã phát hành chưa.
4. Gói 02: hợp đồng sửa lại điều khoản nào.
5. Danh sách ngày lễ áp dụng cho SLA.
6. Tên miền, tài khoản AWS và môi trường triển khai thực tế.
