#!/usr/bin/env bash
# Đồng bộ workbook theo dõi gói thầu (QLDA Cấp Xã Lâm Đồng) vào web app.
#
# Hằng tuần (thứ Sáu):
#   1. Copy file workbook mới vào thư mục docs/ (tên bắt đầu bằng Tracking_, đuôi .xlsx)
#   2. Chạy:  scripts/tracking_sync_weekly.sh            (lấy file mới nhất trong docs/)
#      hoặc:  scripts/tracking_sync_weekly.sh path/to/file.xlsx
#
# Script chạy thử trước, in báo cáo, dừng nếu có lỗi, rồi hỏi xác nhận trước khi ghi.
# Dùng --yes để bỏ qua câu hỏi (không khuyến nghị).
#
# Cần DATABASE_URL của web app. Đặt trong apps/api/.env hoặc export trước khi chạy, ví dụ:
#   export DATABASE_URL=postgresql+asyncpg://qlda:qlda@localhost:5432/qlda

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="$REPO_ROOT/apps/api"
DOCS_DIR="$REPO_ROOT/docs"
PYTHON="$API_DIR/.venv/bin/python"
ALEMBIC="$API_DIR/.venv/bin/alembic"

ASSUME_YES=false
WORKBOOK=""
for arg in "$@"; do
  case "$arg" in
    --yes) ASSUME_YES=true ;;
    -h|--help)
      sed -n '2,14p' "$0"
      exit 0
      ;;
    *) WORKBOOK="$arg" ;;
  esac
done

die() {
  echo "LỖI: $*" >&2
  exit 1
}

# 1. Môi trường -------------------------------------------------------------
[[ -x "$PYTHON" ]] || die "Chưa cài môi trường API. Chạy: cd apps/api && uv sync"

if [[ -f "$API_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$API_DIR/.env"
  set +a
fi
[[ -n "${DATABASE_URL:-}" ]] || die "Thiếu DATABASE_URL (đặt trong apps/api/.env hoặc export)."

# 2. Chọn file workbook -----------------------------------------------------
if [[ -z "$WORKBOOK" ]]; then
  WORKBOOK="$(ls -t "$DOCS_DIR"/Tracking_*.xlsx 2>/dev/null | head -n 1 || true)"
  [[ -n "$WORKBOOK" ]] || die "Không thấy file Tracking_*.xlsx trong $DOCS_DIR"
fi
[[ -f "$WORKBOOK" ]] || die "Không tìm thấy file: $WORKBOOK"
WORKBOOK="$(cd "$(dirname "$WORKBOOK")" && pwd)/$(basename "$WORKBOOK")"
echo "Workbook: $WORKBOOK"
echo "Cập nhật lần cuối: $(date -r "$WORKBOOK" '+%d/%m/%Y %H:%M')"
echo

# 3. Migration (idempotent) -------------------------------------------------
echo "== Áp migration còn thiếu"
(cd "$API_DIR" && "$ALEMBIC" upgrade head)
echo

# 4. Chạy thử ----------------------------------------------------------------
echo "== Chạy thử (không ghi)"
DRY_LOG="$(mktemp)"
trap 'rm -f "$DRY_LOG"' EXIT
(cd "$API_DIR" && "$PYTHON" -m app.services.tracking_sync --file "$WORKBOOK") | tee "$DRY_LOG"
echo

if grep -q "\[error\]" "$DRY_LOG"; then
  die "Workbook có lỗi (dòng [error] ở trên). Sửa workbook rồi chạy lại; chưa ghi gì vào DB."
fi
if grep -q "\[chưa ánh xạ\]" "$DRY_LOG"; then
  echo "Lưu ý: có dòng [chưa ánh xạ]. Các dòng này không được ghi; xem báo cáo ở trên."
fi

# 5. Xác nhận và ghi ----------------------------------------------------------
if [[ "$ASSUME_YES" != true ]]; then
  read -r -p "Ghi các thay đổi trên vào web app? [y/N] " answer
  [[ "$answer" == "y" || "$answer" == "Y" ]] || { echo "Đã hủy. Chưa ghi gì."; exit 0; }
fi

echo "== Ghi vào web app"
(cd "$API_DIR" && "$PYTHON" -m app.services.tracking_sync --file "$WORKBOOK" --apply)
echo
echo "Xong. Kiểm tra lại trên web app."
