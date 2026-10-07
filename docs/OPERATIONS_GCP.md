# Vận hành trên Google Cloud

Thay thế `docs/OPERATIONS.md` (AWS) sau khi chuyển xong; phần chạy local, kiểm thử Playwright, nghiệp vụ hằng ngày và các việc của quản trị trong tài liệu cũ vẫn đúng. Mã hạ tầng: `infra/gcp`. Workflow: `.github/workflows/deploy-gcp.yml`.

## 1. Kiến trúc

| Thành phần | Dịch vụ GCP | Ghi chú |
|---|---|---|
| Web (React, PWA) | **Firebase Hosting** | CDN tĩnh. `/api/**` được rewrite tới Cloud Run (`apps/web/firebase.json`) nên trình duyệt chỉ gọi một địa chỉ |
| API | **Cloud Run** service `api` | CPU luôn cấp (tác vụ chạy lại cảnh báo sau khi ghi là tác vụ nền); `max_instances` giới hạn số kết nối CSDL |
| Worker | Cloud Run service `worker` | đúng 1 instance, luôn chạy; trả 200 trên `$PORT` để Cloud Run giữ nó sống |
| Migration, tạo admin | Cloud Run **Job** `migrate`, `seed` | `migrate` chạy trong mỗi lần triển khai |
| CSDL | **Cloud SQL** PostgreSQL 16, IP riêng | sao lưu 7 ngày và PITR; HA chỉ ở `prod` |
| Tài liệu | **Cloud Storage** bucket `<project>-documents` | không công khai, versioning, trình duyệt tải lên và tải xuống bằng signed URL |
| Bí mật | Secret Manager | `JWT_SECRET`, `DATABASE_URL` |
| Ảnh Docker | Artifact Registry | |
| Giám sát | Cloud Monitoring | 5xx, uptime `/api/v1/health` qua Firebase, worker không chạy, CPU và đĩa Cloud SQL |
| CI/CD | GitHub Actions + Workload Identity Federation | không có khóa dịch vụ nào |
| Email | **chưa chọn** | xem mục 8 |

Hai môi trường là hai **project** riêng (`dev`, `prod`), vùng `asia-southeast1`.

### Hai điểm khác AWS cần biết

1. **Cookie phiên phải tên `__session`.** Firebase Hosting chỉ chuyển tiếp đúng cookie này tới Cloud Run. Terraform đã đặt `REFRESH_COOKIE_NAME=__session`; local vẫn dùng `refresh_token`.
2. **Ký URL không cần khóa.** API ký URL tải lên và tải xuống bằng IAM `signBlob` với chính service account của nó (cần `roles/iam.serviceAccountTokenCreator` trên chính nó; Terraform đã cấp). Không tạo hay lưu file khóa JSON.

## 2. Dựng lần đầu

Cần: hai project GCP có billing, `gcloud`, Terraform ≥ 1.9, quyền Owner trong project để chạy lần đầu.

1. **Bucket trạng thái Terraform** (một lần cho mỗi project):
   ```bash
   gcloud storage buckets create gs://qlda-dev-terraform-state --project=<dev-project-id> \
     --location=asia-southeast1 --uniform-bucket-level-access
   gcloud storage buckets update gs://qlda-dev-terraform-state --versioning
   ```
   Tên bucket phải khớp `envs/<env>.backend.hcl`.
2. Sửa `infra/gcp/envs/<env>.tfvars`: `project_id`, `github_repository`, `web_domain`, `alarm_email`.
3. **Lần apply đầu không có Cloud Run** (chưa có ảnh để chạy):
   ```bash
   cd infra/gcp
   terraform init -backend-config=envs/dev.backend.hcl
   terraform apply -var-file=envs/dev.tfvars -var deploy_services=false
   ```
4. Tạo GitHub environment `dev` (và `prod`) với các biến lấy từ `terraform output`:

   | Biến | Lấy từ |
   |---|---|
   | `GCP_PROJECT_ID` | `project_id` trong tfvars |
   | `GCP_REGION` | `asia-southeast1` |
   | `GCP_WORKLOAD_IDENTITY_PROVIDER` | `workload_identity_provider` |
   | `GCP_DEPLOY_SERVICE_ACCOUNT` | `deploy_service_account` |
   | `ARTIFACT_REPOSITORY` | `artifact_repository` |
   | `FIREBASE_SITE` | `firebase_site_id` |
   | `WEB_URL` | `web_url` |

5. Đẩy ảnh đầu tiên lên Artifact Registry (workflow **Deploy (Google Cloud)** làm bước này nhưng cần Cloud Run job tồn tại), nên lần đầu build tay:
   ```bash
   gcloud auth configure-docker asia-southeast1-docker.pkg.dev
   docker build -t $(terraform output -raw artifact_repository)/api:latest apps/api
   docker push $(terraform output -raw artifact_repository)/api:latest
   ```
6. **Apply lần hai, có Cloud Run:** `terraform apply -var-file=envs/dev.tfvars` (đặt `image_tag` mặc định `latest`).
7. Chạy workflow **Deploy (Google Cloud)** cho môi trường `dev`: build ảnh theo commit, chạy migration, cập nhật `api` và `worker`, đẩy web lên Firebase Hosting, kiểm tra `/api/v1/health`.
8. **Tạo admin đầu tiên:** `gcloud run jobs execute seed --region asia-southeast1 --project <id> --wait`, rồi đọc mật khẩu tạm trong log của job (`gcloud run jobs executions logs ...` hoặc Cloud Logging). **Đổi mật khẩu ngay lần đăng nhập đầu**; sau đó tạo ít nhất một người dùng vai trò Giám đốc.

### Tên miền riêng

Đặt `web_domain` rồi `terraform apply`: Terraform thêm tên miền vào Firebase Hosting; lấy các bản ghi DNS cần tạo ở Firebase console (Hosting → Custom domain) và chờ chứng chỉ được cấp. CORS của bucket tài liệu theo `web_domain` nên cũng được cập nhật. **Truy cập bằng đúng địa chỉ trong `web_url`**: địa chỉ `*.firebaseapp.com` khác origin và việc tải tài liệu lên sẽ bị chặn bởi CORS.

## 3. Triển khai thường ngày

Workflow **Deploy (Google Cloud)** chạy tay, chọn môi trường. Với `prod` hãy bật "Required reviewers" trên GitHub environment. Workflow dừng nếu migration lỗi (dịch vụ chưa bị đổi); Cloud Run không chuyển lưu lượng sang một revision chưa qua kiểm tra sức khỏe.

**Quay lại bản cũ:** Cloud Run → service → *Revisions* → chọn revision trước → *Manage traffic* 100%. Hoặc `gcloud run services update-traffic api --to-revisions=<revision>=100`. Migration chỉ nên viết tương thích lùi (thêm cột, không xóa).

## 4. Sao lưu và khôi phục

| Dữ liệu | Cơ chế | Khôi phục |
|---|---|---|
| CSDL | sao lưu tự động 7 ngày, PITR 7 ngày | Cloud SQL → *Clone* tại một thời điểm vào instance mới; kiểm tra; cập nhật secret `*-database-url` rồi triển khai lại |
| Tài liệu | versioning, giữ phiên bản cũ 365 ngày | `gcloud storage cp gs://bucket/obj#<generation> gs://bucket/obj` |
| Hạ tầng | Git + trạng thái Terraform (bucket có versioning) | `terraform apply` |

**Kiểm tra khôi phục hằng quý:** clone CSDL về thời điểm 24 giờ trước vào instance tạm, chạy `alembic current` và đếm `packages`, `contracts`, `documents`; mở thử 3 tài liệu từ phiên bản cũ; ghi kết quả vào nhật ký vận hành; xóa instance tạm.

## 5. Giám sát

Chính sách cảnh báo gửi email tới `alarm_email`:

| Cảnh báo | Việc đầu tiên cần làm |
|---|---|
| API 5xx > 5 trong 5 phút | Cloud Logging, lọc `resource.labels.service_name="api"` và `severity>=ERROR`; xem lần triển khai gần nhất |
| API không trả lời (uptime check) | Cloud Run → `api` → revisions; Cloud SQL còn chạy không |
| Worker không chạy 10 phút | Cloud Run → `worker`; đảm bảo `min=max=1` |
| Cloud SQL CPU > 80% | xem truy vấn chậm; tăng `db_tier` |
| Cloud SQL đĩa > 85% | tăng `db_disk_gb` (tự giãn) |

Số kết nối: mỗi tiến trình giữ tối đa `db_pool_size + db_max_overflow`. Tổng (`api_max_instances` + 1 worker + job) × con số đó phải nhỏ hơn `max_connections` của tier (tier nhỏ chỉ cho vài chục kết nối).

## 6. Bí mật

| Bí mật | Cách xoay |
|---|---|
| `JWT_SECRET` | thêm phiên bản mới của secret `qlda-<env>-jwt-secret` rồi triển khai lại; mọi phiên đăng nhập hiện tại hết hiệu lực |
| Mật khẩu CSDL | `terraform apply -replace=random_password.db` (cập nhật cả người dùng Cloud SQL và `DATABASE_URL`), rồi triển khai lại |
| Người dùng ứng dụng | `/admin/users` → *Cấp lại mật khẩu* |

## 7. Giới hạn đã biết (chưa kiểm chứng trên GCP thật)

- Terraform qua `terraform validate` và `fmt`, **chưa `apply` vào project thật**.
- `GcsStorage` được kiểm bằng khóa ký thật ở máy cá nhân và client giả; **chưa chạy với bucket GCS thật**: lần dựng dev đầu tiên hãy thử tải lên một tệp 50 MB từ trình duyệt, tải xuống, xóa, và kiểm quyền `signBlob`. Nếu `signBlob` bị từ chối, kiểm `roles/iam.serviceAccountTokenCreator` trên chính service account `qlda-<env>-app` và API IAM Credentials đã bật.
- CSP của Firebase Hosting đã thử với bản build trong Chromium (7 trang, không vi phạm); chưa thử tải lên thật vì cần GCS (`connect-src` cho phép `https://storage.googleapis.com`).
- Chính sách tổ chức "Domain restricted sharing" có thể chặn `allUsers` gọi Cloud Run (Firebase Hosting cần quyền này). Nếu `terraform apply` lỗi ở `api_public`, nhờ quản trị tổ chức cho phép ngoại lệ cho project này.
- Firebase Hosting giới hạn mỗi yêu cầu rewrite tới Cloud Run 60 giây; tải tài liệu đi thẳng vào bucket nên không bị ảnh hưởng.

## 8. Email (đang hoãn)

GCP không có dịch vụ gửi email. Tạm thời `MAIL_BACKEND=memory`: engine cảnh báo vẫn chạy, nhưng email chỉ được ghi nhận trong bộ nhớ, **không gửi đi**. Cần một nhà cung cấp SMTP (SendGrid, Mailgun, Brevo, Resend...) rồi:

1. thêm đăng nhập và STARTTLS vào `SmtpMailer` (hiện chưa có), cấu hình qua `SMTP_USER`, `SMTP_PASSWORD` trong Secret Manager,
2. gỡ `SesMailer`,
3. đặt `mail_backend = "smtp"` trong tfvars.
Gửi qua cổng 587 hoặc 465 (GCP chặn cổng 25).
