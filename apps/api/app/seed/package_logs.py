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
        "seed:g05-bbbg-1310",
        5,
        date(2026, 10, 13),
        (
            "Biên bản bàn giao thiết bị số 1310/BBBG-G05/TVGS-SGM, lập 09:00 ngày 13/10/2026 "
            "tại 192 Phạm Hùng, Phường Phú Thủy, Tỉnh Lâm Đồng, theo Hợp đồng 72/2026/HĐ/"
            "SKHCNLĐ-LD P&N-BSN ngày 14/9/2026. Bên giao: liên danh P&N – BSN (ông Phạm "
            "Trọng Khải, Giám đốc P&N); bên nhận: Sở KH&CN (ông Võ Thành Công, Giám đốc); TVQLDA "
            "(ông Cát Nghiêm Hiếu Tuấn); TVGS (ông Võ Minh Thanh).\n"
            "Thiết bị bàn giao: máy tính xách tay Asus P1503CVA 150 bộ (BSN); máy in Brother "
            "HL-B2100D 75; thiết bị thu nhận mống mắt CMITech BMT-20 75; đầu đọc thẻ uTrust "
            "4701F 75; máy ảnh Canon EOS R50 kèm ống kính RF-S18-45mm 75 (thân máy 75 số, ống "
            "kính 75 số); phần mềm VAGOGE RAR-EP PREMIUM 150 bản quyền 03 năm; phụ kiện 75 bộ "
            "gồm khung treo phông KTP, chân máy ảnh Benro T980, cáp Ugreen USB-A to USB-C, hub "
            "Ugreen (không có serial). Các hạng mục còn lại do P&N giao.\n"
            "Bảo hành: 24 tháng máy tính xách tay; 12 tháng máy in, thiết bị mống mắt, đầu đọc "
            "thẻ, máy ảnh, phụ kiện; 03 năm phần mềm; xử lý trong 04 giờ (8h00–17h00) hoặc 10 "
            "giờ (ngoài giờ), khoản 9.3 Điều 9."
        ),
        (
            "(1) Chưa bàn giao trong biên bản này: thiết bị thu nhận vân tay BKCONTECH "
            "BKCA2020101 (75 bộ) và pin dự phòng của mục phụ kiện; sẽ bàn giao bổ sung bằng "
            "biên bản riêng.\n"
            "(2) Serial máy tính xách tay: TT 145–150 có số serial ở phụ lục CQ của hãng bị dấu "
            "đỏ che một phần; TT 148 (TBNXCV16W00248G), 149 (W4NXCV06V972168), 150 "
            "(W4NXCV06V981165) khác dải số với các máy còn lại; đối chiếu tem trên máy khi bàn "
            "giao.\n"
            "(3) Thiết bị mống mắt: CO-CQ lô CMIT20260923-1 ghi 100 số serial, Gói 05 giao 75; "
            "nhà thầu xác định 75 số thực giao.\n"
            "(4) Máy in: danh mục 75 serial do P&N lập ngày 12/10/2026; TT 1–59 trùng danh sách "
            "kèm chứng nhận chất lượng của Brother Việt Nam ngày 09/10/2026.\n"
            "(5) Mục III (tình trạng thiết bị khi bàn giao, 6 nội dung) và mục IV (ý kiến các "
            "bên) chưa được đánh dấu hay ghi; số bản lập chưa ghi; tiêu đề phụ lục còn để trống "
            "số biên bản."
        ),
        (
            "Hoàn thiện mục III và IV, ghi số bản và ký biên bản bàn giao; bàn giao bổ sung "
            "thiết bị vân tay BKCA2020101 (75 bộ) và pin dự phòng bằng biên bản riêng; đối chiếu "
            "serial TT 145–150 của máy tính xách tay với tem trên máy; tải bản ký lên hồ sơ gói."
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
