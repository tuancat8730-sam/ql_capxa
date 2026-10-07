# Tài liệu vận hành

Dành cho người triển khai và vận hành hệ thống QLDA Cấp xã (quản trị hệ thống, kỹ sư DevOps). Nghiệp vụ nằm ở `docs/SPEC.md`, tiến độ phát triển ở `docs/PROGRESS.md`.

## 1. Tổng quan

| Thành phần | Chạy ở đâu | Ghi chú |
|---|---|---|
| Web (React, PWA) | S3 riêng + CloudFront | CloudFront cũng chuyển `/api/*` về ALB: cùng một địa chỉ, cookie đăng nhập không cần CORS |
| API (FastAPI) | ECS Fargate, sau ALB HTTPS | `GET /api/v1/health` là điểm kiểm tra sức khỏe |
| Worker (APScheduler) | ECS Fargate, **đúng 1 tác vụ** | chạy engine cảnh báo hằng giờ và email tóm tắt 08:00 (giờ Việt Nam) |
| CSDL | RDS PostgreSQL 16 | Multi-AZ chỉ bật ở `prod`; sao lưu tự động 7 ngày |
| Tài liệu | S3 riêng, mã hóa SSE-S3, bật versioning | trình duyệt tải lên và tải xuống trực tiếp bằng presigned URL |
| Email | Amazon SES | người gửi cấu hình bằng `ses_sender` |
| Bí mật | Secrets Manager | `JWT_SECRET`, `DATABASE_URL`; không có bí mật trong ảnh Docker hay mã nguồn |
| Nhật ký, cảnh báo | CloudWatch | nhóm log `/qlda/<môi trường>/{api,worker,migrate}` |

Hai môi trường là hai workspace Terraform: `dev` và `prod`, mỗi môi trường có tài khoản dữ liệu riêng.

## 2. Chạy trên máy cá nhân

```bash
make up          # Postgres, MinIO, API, worker, web, mailpit (docker compose)
make seed        # tạo admin, dự án, 8 gói, hợp đồng, bảo lãnh, rủi ro, danh mục hồ sơ (chạy lại không trùng)
make test        # pytest và vitest
make lint        # ruff, mypy, tsc, oxlint
```

- `make seed` in ra mật khẩu tạm của tài khoản `admin@qlda.local`; đăng nhập lần đầu sẽ bắt đổi mật khẩu. Đặt trước bằng `SEED_ADMIN_PASSWORD`.
- Email thử nghiệm xem ở mailpit: http://localhost:8025.
- `.env.example` là mẫu đầy đủ các biến cấu hình, không chứa bí mật thật.

### Kiểm thử Playwright (5 luồng của SPEC mục 11)

```bash
cd apps/web
pnpm exec playwright install chromium     # một lần
pnpm exec playwright test                 # tự dựng CSDL mới, S3 giả (moto), API và Vite
```

`scripts/e2e-stack.sh` tạo CSDL `qlda_e2e` mới mỗi lần, nạp dữ liệu mẫu và tài khoản `*@e2e.test`. Script từ chối chạy trên CSDL không có đuôi `_e2e`. Cần Postgres của `make up`; trên CI dùng `E2E_PSQL=local`. Nếu máy thiếu thư viện hệ thống cho Chromium: `pnpm exec playwright install-deps chromium` (cần sudo).

## 3. Dựng hạ tầng AWS lần đầu

Mã nằm ở `infra/terraform`. Cần Terraform ≥ 1.9 và quyền quản trị trong tài khoản AWS.

1. **Kho trạng thái:** tạo thủ công một bucket S3 (bật versioning, mã hóa) và bảng DynamoDB `qlda-terraform-locks` (khóa chính `LockID`). Sửa tên bucket trong `envs/dev.backend.hcl` và `envs/prod.backend.hcl`.
2. **Chứng chỉ ACM:** một chứng chỉ trong `ap-southeast-1` cho `api_domain` (ALB); nếu dùng tên miền riêng cho web thì thêm chứng chỉ trong `us-east-1` (`web_certificate_arn`).
3. **SES:** `ses_sender` phải xác minh được. Địa chỉ email: bấm liên kết AWS gửi tới. Tên miền: thêm các bản ghi DKIM. Tài khoản SES mới ở chế độ sandbox, cần xin nâng lên production để gửi tới địa chỉ chưa xác minh.
4. Sửa `envs/<môi trường>.tfvars` (tên miền, ARN chứng chỉ, `github_repository`...).
5. Chạy:

```bash
cd infra/terraform
terraform init -backend-config=envs/dev.backend.hcl
terraform workspace new dev || terraform workspace select dev
terraform apply -var-file=envs/dev.tfvars
```

6. Lần đầu ECR còn trống nên dịch vụ ECS chưa khởi động được. Chạy workflow **Deploy** (mục 4) để đưa ảnh đầu tiên lên, hoặc đẩy ảnh bằng tay.
7. Tạo tài khoản quản trị đầu tiên: chạy một tác vụ một lần với lệnh `python -m app.seed.run` (dùng task definition `qlda-<env>-migrate`, ghi đè lệnh), đọc mật khẩu tạm trong log `/qlda/<env>/migrate`. **Đổi mật khẩu ngay khi đăng nhập lần đầu**, sau đó đổi `SEED_ADMIN_PASSWORD` nếu chạy lại.
8. Trỏ DNS: nếu không dùng Route 53, tạo CNAME từ `api_domain` tới `alb_dns_name` và từ `web_domain` tới `cloudfront_domain` (đều có trong `terraform output`).

Trong dev có thể để `web_domain = ""`, web chạy ở địa chỉ `*.cloudfront.net`.

## 4. Triển khai (GitHub Actions, OIDC, không lưu khóa)

Workflow **Deploy** (`.github/workflows/deploy.yml`) chạy tay, chọn `dev` hoặc `prod`:

1. build và đẩy ảnh API lên ECR (gắn nhãn theo commit),
2. đăng ký bản task definition mới cho `api`, `worker`, `migrate`,
3. **chạy migration** bằng tác vụ một lần; nếu mã thoát khác 0 thì dừng, dịch vụ chưa bị đổi,
4. cập nhật dịch vụ `api` và `worker`, chờ ổn định (circuit breaker tự quay lại bản cũ nếu tác vụ mới không khỏe),
5. build web, đẩy lên S3 (tài nguyên có mã băm cache 1 năm; `index.html`, `sw.js`, `manifest` luôn kiểm tra lại), vô hiệu hóa CloudFront.

Cần tạo **GitHub environment** `dev` và `prod`, với các biến lấy từ `terraform output`:

| Biến | Lấy từ |
|---|---|
| `AWS_ROLE_ARN` | `deploy_role_arn` |
| `ECR_REPOSITORY` | phần tên của `ecr_repository_url` (sau dấu `/`) |
| `WEB_BUCKET`, `CLOUDFRONT_DISTRIBUTION_ID` | `web_bucket`, `cloudfront_distribution_id` |
| `PRIVATE_SUBNETS` | `private_subnet_ids`, nối bằng dấu phẩy |
| `ECS_SECURITY_GROUP` | `ecs_security_group_id` |

Với `prod` nên bật "Required reviewers" trên GitHub environment. Vai trò triển khai chỉ nhận token của job chạy trong environment tương ứng của đúng kho mã.

**Quay lại bản cũ:** trong ECS, chọn task definition ở bản trước và cập nhật dịch vụ (`aws ecs update-service --task-definition <arn cũ>`). Migration chỉ nên viết tương thích lùi (thêm cột, không xóa) để quay lại an toàn.

## 5. Sao lưu và khôi phục (SPEC 4.17)

| Dữ liệu | Cơ chế | Khôi phục |
|---|---|---|
| CSDL | RDS sao lưu tự động 7 ngày, khôi phục theo thời điểm; `prod` có bản chụp cuối khi xóa | RDS → *Restore to point in time* vào một instance mới, kiểm tra, rồi đổi `DATABASE_URL` trong Secrets Manager và khởi động lại dịch vụ |
| Tài liệu | S3 versioning, giữ bản cũ 365 ngày | bỏ dấu xóa (delete marker) hoặc sao chép lại phiên bản trước |
| Mã hạ tầng | Git + trạng thái Terraform trong S3 versioned | `terraform apply` |

**Kiểm tra khôi phục hằng quý** (yêu cầu SPEC):

1. khôi phục bản sao CSDL ở thời điểm 24 giờ trước vào instance tạm,
2. chạy `alembic current` và đếm bản ghi `packages`, `contracts`, `documents`,
3. mở thử 3 tài liệu ngẫu nhiên từ phiên bản S3 cũ,
4. ghi kết quả (ngày, người làm, thời gian khôi phục) vào nhật ký vận hành, xóa instance tạm.

## 6. Giám sát

Cảnh báo CloudWatch gửi về chủ đề SNS `qlda-<env>-alarms` (gắn email bằng `alarm_email`):

| Cảnh báo | Nghĩa | Việc đầu tiên cần làm |
|---|---|---|
| `api-5xx` | API trả lỗi 5xx > 5 lần trong 5 phút | xem log `/qlda/<env>/api`, kiểm tra lần triển khai gần nhất |
| `api-unhealthy` | không còn tác vụ API khỏe | ECS → dịch vụ `api` → sự kiện; xem RDS có còn kết nối được không |
| `api-cpu`, `db-cpu` | CPU > 80% trong 10 phút | xem số yêu cầu, truy vấn chậm; tăng `api_cpu`, `api_desired_count` hoặc `db_instance_class` |
| `db-storage` | còn dưới 2 GB | tăng `db_allocated_storage` (tự giãn tới 5 lần) |

Ngoài ra: ALB chỉ mở 443 (80 chuyển hướng), API và RDS nằm trong mạng riêng, RDS chỉ nhận kết nối từ tác vụ ECS. Mọi phản hồi của API có `Content-Security-Policy`, `X-Frame-Options`, `nosniff` (và HSTS khi `COOKIE_SECURE=true`); CloudFront gắn bộ tiêu đề tương ứng cho web.

## 7. Cảnh báo và email trong ứng dụng

- Worker chạy engine mỗi giờ (phút 0), email tóm tắt lúc 08:00. Ngoài ra mỗi thay đổi dữ liệu liên quan kích hoạt một lượt chạy nền (`ALERT_REFRESH_ON_WRITE`).
- Một khóa advisory của Postgres đảm bảo chỉ một tiến trình chạy engine và gửi email tại một thời điểm, nên chạy nhiều tác vụ API vẫn không gửi trùng email.
- Admin hoặc Giám đốc có thể bấm **Kiểm tra lại ngay** ở `/alerts` (hoặc `POST /api/v1/alerts/refresh`).
- Email cảnh báo nghiêm trọng gửi tới Giám đốc QLDA và người được gán. **Không có người dùng vai trò `director` đang hoạt động thì không ai nhận email**; hãy tạo ít nhất một.

### Khi email không tới

1. Log `/qlda/<env>/worker` và `/qlda/<env>/api`: tìm `critical alert e-mail to ... failed`. Alert chỉ được đánh dấu đã gửi khi mọi người nhận đều nhận được, lần chạy sau sẽ thử lại.
2. SES: người gửi đã xác minh chưa, tài khoản còn ở sandbox không, có bị giới hạn hạn mức hay tỉ lệ bounce không.
3. Quyền: vai trò tác vụ chỉ được gửi từ địa chỉ `ses_sender`; đổi `ses_sender` thì áp dụng lại Terraform.

## 8. Quản lý bí mật

| Bí mật | Cách xoay |
|---|---|
| `JWT_SECRET` | Secrets Manager → tạo giá trị mới → khởi động lại dịch vụ `api`. Mọi phiên đăng nhập hiện tại hết hiệu lực, người dùng đăng nhập lại |
| Mật khẩu CSDL | đổi `random_password.db` bằng `terraform apply -replace=random_password.db` (cập nhật cả RDS và `DATABASE_URL`), sau đó khởi động lại `api` và `worker` |
| Mật khẩu người dùng | admin dùng *Cấp lại mật khẩu* ở `/admin/users`; tài khoản bị khóa 15 phút sau 5 lần nhập sai |

Không đưa bí mật vào biến Terraform dạng văn bản hay vào GitHub; nếu nghi ngờ lộ, xoay ngay rồi xem `/admin/audit`.

## 9. Việc hằng ngày của quản trị

- `/admin/audit` (admin, giám đốc): ai đã tạo, sửa, xóa, đăng nhập, tải tài liệu nhạy cảm, xuất dữ liệu; lọc theo thao tác, đối tượng, người dùng, ngày. Giờ hiển thị luôn là giờ Việt Nam.
- `/admin/settings` (admin): danh sách ngày nghỉ lễ. **Cần nhập ngày lễ mỗi năm**, vì hạn xử lý vướng mắc cấp 2 (3 ngày làm việc) bỏ qua các ngày này.
- `/admin/users`: tạo người dùng, gán vai trò, khóa tài khoản (không xóa người đã có dữ liệu).
- Tài liệu nhạy cảm: quyền xem theo từng gói ở tab *Hồ sơ* của gói; mọi lượt tải được ghi nhật ký.

## 10. Chi phí (ước lượng dev)

Khoản lớn nhất là NAT gateway (một cái ở dev) và RDS `db.t4g.micro`. Để tiết kiệm có thể dừng `worker` và `api` ngoài giờ (`desired_count = 0`) và dừng instance RDS tối đa 7 ngày. `prod` dùng hai NAT, RDS Multi-AZ và hai tác vụ API nên đắt hơn nhiều.

## 11. Giới hạn đã biết

- Terraform đã được kiểm tra cú pháp và tính hợp lệ (`terraform validate`), nhưng **chưa áp dụng thử lên tài khoản AWS thật**; lần `apply` đầu cần người có quyền theo dõi.
- Ảnh Docker đã build và chạy thử migration, API, worker trên máy cá nhân; chưa chạy trên Fargate.
- Chưa có quét virus tệp tải lên (SPEC để là điểm gắn, chưa bắt buộc).
- Danh sách câu hỏi nghiệp vụ còn mở nằm ở `docs/OPEN_QUESTIONS.md`.
