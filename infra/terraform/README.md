# Hạ tầng AWS

Hướng dẫn đầy đủ (dựng lần đầu, triển khai, sao lưu, giám sát) nằm ở [`docs/OPERATIONS.md`](../../docs/OPERATIONS.md).

```bash
terraform init -backend-config=envs/dev.backend.hcl
terraform workspace new dev || terraform workspace select dev
terraform plan  -var-file=envs/dev.tfvars
terraform apply -var-file=envs/dev.tfvars
```

Hai workspace: `dev` và `prod` (tài nguyên đặt tên `qlda-<workspace>`). Kiểm tra mã không cần tài khoản AWS:

```bash
terraform init -backend=false && terraform validate && terraform fmt -check -recursive
```
