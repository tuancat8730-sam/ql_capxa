"""Initial risk register from SPEC 14.6.

The spec names the ten risks but gives no probability/impact/owner/due date, so the scores below are
an initial assessment for the team to review (docs/OPEN_QUESTIONS.md #24). Owners and due dates are
left empty rather than invented.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Package, Risk
from app.seed.project import capxa_project
from app.services.risk_rules import risk_score


@dataclass(frozen=True)
class RiskSeed:
    title: str
    description: str
    category: str
    probability: int
    impact: int
    mitigation: str
    source: str
    package: int | None = None


RISKS: tuple[RiskSeed, ...] = (
    RiskSeed(
        "Gói 03 chưa rõ nghiệm thu, thanh lý, thanh toán; chứng thư thẩm định giá hết hiệu lực",
        "Chứng thư thẩm định giá (194.717.303.146 đ, 20/6/2026) hết hiệu lực khoảng 20/9/2026 "
        "trong khi các gói thiết bị còn đang thực hiện; QĐ 154 ghi nhầm tên dự án cần đính chính.",
        "contract",
        4,
        5,
        "Xác nhận nghiệm thu, thanh lý và thanh toán HĐ 41; đề nghị đính chính QĐ 154; "
        "kiểm tra chứng thư có còn được dùng làm căn cứ không.",
        "analysis",
        3,
    ),
    RiskSeed(
        "Bảo lãnh tạm ứng Gói 05 hết hạn trước hoặc sát hạn hợp đồng",
        "Bảo lãnh TPBank và BIDV hết hạn khoảng 13/11/2026, hợp đồng kết thúc 12/11/2026.",
        "contract",
        5,
        4,
        "Yêu cầu nhà thầu gia hạn bảo lãnh tạm ứng trước khi hết hạn; đối chiếu bản gốc.",
        "analysis",
        5,
    ),
    RiskSeed(
        "Thiếu bảo lãnh Gói 04 (tạm ứng) và Gói 05 (thực hiện hợp đồng)",
        "Chưa có bảo lãnh tạm ứng Gói 04 (15.451.620.000) và "
        "bảo đảm thực hiện Gói 05 (407.999.250).",
        "contract",
        4,
        4,
        "Nhắc nhà thầu nộp bảo lãnh; chưa tạm ứng khi chưa có bảo lãnh.",
        "analysis",
    ),
    RiskSeed(
        "Gói 02 có điều khoản hợp đồng sai khác",
        "Thiết kế thi công, điều chỉnh giá so với trọn gói, 90 so với 60 ngày, tài khoản "
        "9552.2.8171939 khác 8200685, phạt 10%/tuần tối đa 20%, nhắc GIS.",
        "contract",
        5,
        3,
        "Rà soát và ký phụ lục sửa đổi cho khớp KHLCNT trước khi thanh toán.",
        "analysis",
        2,
    ),
    RiskSeed(
        "Gói 01 và Gói 02 có thể phải gia hạn",
        "Ngày kết thúc hợp đồng sát hạn và có sai khác giữa văn bản.",
        "schedule",
        3,
        2,
        "Theo dõi tiến độ giao hàng; lập đề xuất gia hạn sớm nếu cần.",
        "analysis",
    ),
    RiskSeed(
        "Gói 04 giá trúng thấp hơn giá gói thầu 17,3%: rủi ro chất lượng",
        "Giá trúng 51.505.400.000 so với giá gói thầu 62.298.200.000.",
        "quality",
        3,
        4,
        "Tăng cường kiểm tra CO, CQ và kiểm định khi nghiệm thu; yêu cầu mẫu đối chứng.",
        "analysis",
        4,
    ),
    RiskSeed(
        "Thời gian kiểm định, hiệu chuẩn thiết bị kéo dài",
        "Thiết bị yêu cầu kiểm định hoặc hiệu chuẩn có thể làm chậm nghiệm thu.",
        "schedule",
        3,
        3,
        "Lập kế hoạch kiểm định sớm; thống nhất đơn vị kiểm định với nhà thầu.",
        "de_cuong",
    ),
    RiskSeed(
        "Chia thanh toán giữa các thành viên liên danh",
        "Gói 04 (60%/40%) và Gói 05 cần phân chia thanh toán, tạm ứng theo thành viên.",
        "cost",
        2,
        3,
        "Ghi rõ tỷ lệ và tài khoản từng thành viên trong hồ sơ thanh toán.",
        "de_cuong",
    ),
    RiskSeed(
        "Hợp đồng TVGS (~13/12/2026) kết thúc trước gói cung cấp cuối cùng",
        "Giám sát có thể không còn hiệu lực khi các gói cung cấp còn nghiệm thu.",
        "contract",
        3,
        4,
        "Chuẩn bị gia hạn hợp đồng TVGS theo tiến độ gói cung cấp.",
        "analysis",
    ),
    RiskSeed(
        "Chậm bàn giao mặt bằng, điện, mạng tại xã",
        "Điều kiện lắp đặt tại các xã chưa sẵn sàng làm chậm giao và lắp thiết bị.",
        "supply",
        4,
        3,
        "Gửi lịch giao hàng sớm cho xã; theo dõi điều kiện mặt bằng trước khi giao.",
        "de_cuong",
    ),
)


async def seed_risks(session: AsyncSession) -> None:
    """Requires `seed_project`. Idempotent: matches existing risks by title."""
    project = await capxa_project(session)
    if project is None:
        return
    packages = {
        p.number: p.id
        for p in (await session.execute(select(Package).where(Package.project_id == project.id)))
        .scalars()
        .all()
    }
    existing = set(
        (await session.execute(select(Risk.title).where(Risk.project_id == project.id)))
        .scalars()
        .all()
    )
    last = len(existing)
    for seed in RISKS:
        if seed.title in existing:
            continue
        last += 1
        session.add(
            Risk(
                code=f"R-{last:03d}",
                project_id=project.id,
                package_id=packages.get(seed.package) if seed.package else None,
                title=seed.title,
                description=seed.description,
                category=seed.category,
                probability=seed.probability,
                impact=seed.impact,
                score=risk_score(seed.probability, seed.impact),
                mitigation=seed.mitigation,
                status="open",
                source=seed.source,
            )
        )
    await session.commit()
