"""Site-diary entries taken from documents in `data_documents`.

Each entry has a fixed `client_id`, so a rerun adds nothing and an entry someone edited in the
application is left alone.
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Package, ProgressLog, User
from app.seed.project import capxa_project


@dataclass(frozen=True)
class LogSeed:
    client_id: str
    package: int
    log_date: date
    summary: str
    issues: str | None
    next_steps: str | None


LOGS: tuple[LogSeed, ...] = (
    LogSeed(
        "seed:g05-bbdk-v2",
        5,
        date(2026, 10, 15),
        (
            "Biên bản kiểm tra điều kiện triển khai và hồ sơ kỹ thuật hàng hóa trước khi cung "
            "cấp, lắp đặt (mẫu BM-03, số …/BBĐK-G05/TVGS-SGM, bản v2 của TVGS Sài Gòn Mới; "
            "chưa ghi ngày và giờ lập). Địa điểm: kho tập kết tại Phan Thiết. Thành phần: "
            "TVQLDA (Cát Nghiêm Hiếu Tuấn), TVGS (Võ Minh Thanh), liên danh P&N (Phạm Trọng "
            "Khải, đứng đầu) và BSN (Phạm Văn Duy).\n"
            "Kết luận: điều kiện triển khai ĐẠT; hồ sơ kỹ thuật hàng hóa PHÙ HỢP.\n"
            "A. Điều kiện triển khai, 9/9 mục đạt: kế hoạch và tiến độ chi tiết theo đợt, khu "
            "vực, 75 Công an xã/phường/đặc khu (60 ngày từ ngày hợp đồng có hiệu lực, đến hết "
            "13/11/2026); nhân sự kỹ thuật và tổ lắp đặt; kho tập kết (mái che, PCCC, chống "
            "ẩm); bảo hiểm hàng hóa; danh sách phân bổ (mỗi đơn vị 02 máy tính xách tay, 02 bản "
            "quyền phần mềm, 01 bộ mỗi thiết bị còn lại); an toàn điện và bảo mật; bảo đảm "
            "thực hiện 407.999.250 đ cùng bảo lãnh tạm ứng P&N 2.815.942.500 đ và BSN "
            "1.264.050.000 đ; phương án bảo hành, bảo trì; kế hoạch đào tạo.\n"
            "B. Hồ sơ kỹ thuật, 9/9 hạng mục phù hợp: máy tính xách tay Asus P1503CVA (150 bộ, "
            "bảo hành 24 tháng); máy in Brother HL-B2100D (75); đầu thu vân tay BKCONTECH "
            "BKCA2020101 (75); đầu thu mống mắt CMITech BTM-20 (75); đầu đọc thẻ uTrust 4701F "
            "(75); máy ảnh Canon EOS R50 (75); phần mềm VAGOGE RAR-EP PREMIUM (150 license, 03 "
            "năm); phụ kiện (75 bộ); cài đặt, cấu hình, vận chuyển do P&N thực hiện."
        ),
        (
            "Hai điểm khác giữa E-HSMT và hợp đồng; hàng hóa được kiểm tra theo hợp đồng "
            "(thứ tự ưu tiên tài liệu tại Điều 2): (1) thiết bị thu vân tay: hợp đồng IP54, "
            "E-HSMT tối thiểu IP57; (2) máy tính xách tay: hợp đồng Core i5 Processor 210H, "
            "E-HSMT tối thiểu Core i5 1334U thế hệ 13. Nội dung và thời hạn bổ sung: không có. "
            "Biên bản chưa có số, ngày và chữ ký."
        ),
        (
            "Nhà thầu được nhập và tập kết hàng tại kho. Trước mỗi lô hàng gửi TVGS danh sách "
            "serial (Excel), phiếu đóng gói, CO, CQ và thông báo lịch kiểm tra tại kho trước "
            "tối thiểu 02 ngày làm việc để kiểm tra theo mẫu BM-04. Ký, ghi ngày và số biên "
            "bản; tải bản ký lên hồ sơ gói."
        ),
    ),
)


async def seed_package_logs(session: AsyncSession) -> None:
    project = await capxa_project(session)
    author = (
        await session.execute(
            select(User).where(User.role == "admin").order_by(User.created_at).limit(1)
        )
    ).scalar_one_or_none()
    if project is None or author is None:
        return
    for seed in LOGS:
        done = (
            await session.execute(
                select(ProgressLog.id).where(ProgressLog.client_id == seed.client_id)
            )
        ).first()
        package = (
            await session.execute(
                select(Package).where(
                    Package.project_id == project.id, Package.number == seed.package
                )
            )
        ).scalar_one_or_none()
        if done or package is None:
            continue
        session.add(
            ProgressLog(
                package_id=package.id,
                log_date=seed.log_date,
                progress_pct=package.progress_pct,
                summary=seed.summary,
                issues=seed.issues,
                next_steps=seed.next_steps,
                author_id=author.id,
                client_id=seed.client_id,
            )
        )
    await session.commit()
