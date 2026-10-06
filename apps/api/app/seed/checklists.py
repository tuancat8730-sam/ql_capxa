"""Standard document checklist templates (SPEC 4.7, 14.8) and per-package instantiation."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChecklistTemplate, Package
from app.services.documents import instantiate_checklist

S2, S3, S4, S5 = "S2_SELECTION", "S3_EXECUTION", "S4_ACCEPTANCE", "S5_PAYMENT_SETTLEMENT"


@dataclass(frozen=True)
class Tpl:
    stage: str
    doc_type: str
    title: str
    required: bool = True
    due_offset_days: int | None = None
    condition: str | None = None


GOODS: tuple[Tpl, ...] = (
    # S2: selection
    Tpl(S2, "etbmt_approval", "Quyết định phê duyệt E-HSMT"),
    Tpl(S2, "etbmt", "E-TBMT"),
    Tpl(S2, "bid_opening_minutes", "Biên bản mở thầu"),
    Tpl(S2, "evaluation_report", "Báo cáo đánh giá E-HSDT"),
    Tpl(S2, "appraisal_report", "Báo cáo thẩm định KQLCNT"),
    Tpl(S2, "decision_selection_result", "Quyết định phê duyệt KQLCNT"),
    Tpl(S2, "acceptance_letter", "Thư chấp thuận E-HSDT và trao hợp đồng"),
    # S2 -> S3: contract signing
    Tpl(S3, "contract", "Hợp đồng"),
    Tpl(S3, "contract_completion_minutes", "Biên bản hoàn thiện hợp đồng"),
    Tpl(
        S3,
        "guarantee_performance",
        "Bảo lãnh thực hiện hợp đồng",
        due_offset_days=7,
        condition="Hạn: ngày hiệu lực + 7 ngày",
    ),
    Tpl(
        S3,
        "guarantee_advance",
        "Bảo lãnh tạm ứng",
        due_offset_days=0,
        condition="Phải có trước khi tạm ứng",
    ),
    Tpl(S3, "other", "Mẫu 02.a (đề nghị tạm ứng)"),
    # S3: execution
    Tpl(S3, "delivery_plan", "Kế hoạch giao hàng chi tiết"),
    Tpl(S3, "delivery_notice", "Thông báo lịch giao hàng"),
    Tpl(S3, "meeting_minutes", "Biên bản họp khởi động gói (QL-04)"),
    Tpl(S3, "site_inspection_minutes", "Biên bản kiểm tra hiện trường (QL-08)"),
    Tpl(S3, "coc_cq", "CO, CQ"),
    Tpl(S3, "other", "Chứng nhận bảo hành", required=False, condition="Nếu có"),
    Tpl(
        S3,
        "calibration_cert",
        "Chứng nhận kiểm định, hiệu chuẩn",
        required=False,
        condition="Nếu có",
    ),
    # S4: acceptance
    Tpl(S4, "supervisor_report", "Báo cáo kết quả giám sát của TVGS"),
    Tpl(S4, "other", "Biên bản vận hành thử"),
    Tpl(S4, "acceptance_minutes", "Biên bản nghiệm thu (QL-09)"),
    Tpl(S4, "handover_minutes", "Biên bản bàn giao cho đơn vị thụ hưởng (QL-10)"),
    # S5: payment and settlement
    Tpl(S5, "value_statement", "Bảng xác định giá trị khối lượng (QL-11)"),
    Tpl(S5, "invoice", "Hóa đơn"),
    Tpl(S5, "guarantee_warranty", "Bảo lãnh bảo hành"),
    Tpl(S5, "liquidation_minutes", "Biên bản thanh lý (QL-15)"),
    Tpl(S5, "settlement_checklist", "Danh mục hồ sơ quyết toán (QL-16)"),
)

CONSULTING: tuple[Tpl, ...] = (
    Tpl(S2, "decision_selection_result", "Quyết định phê duyệt KQLCNT"),
    Tpl(S3, "contract", "Hợp đồng"),
    Tpl(S3, "contract_completion_minutes", "Biên bản hoàn thiện hợp đồng"),
    Tpl(S3, "other", "Sản phẩm bàn giao theo hợp đồng"),
    Tpl(S4, "acceptance_minutes", "Biên bản nghiệm thu"),
    Tpl(S5, "value_statement", "Bảng xác định khối lượng (QL-11)"),
    Tpl(S5, "invoice", "Hóa đơn"),
    Tpl(S5, "liquidation_minutes", "Biên bản thanh lý (QL-15)"),
)


async def seed_checklist_templates(session: AsyncSession) -> None:
    for package_type, templates in (("goods", GOODS), ("consulting", CONSULTING)):
        for order, t in enumerate(templates):
            exists = (
                await session.execute(
                    select(ChecklistTemplate.id).where(
                        ChecklistTemplate.package_type == package_type,
                        ChecklistTemplate.stage_code == t.stage,
                        ChecklistTemplate.doc_type == t.doc_type,
                        ChecklistTemplate.title == t.title,
                    )
                )
            ).first()
            if exists:
                continue
            session.add(
                ChecklistTemplate(
                    package_type=package_type,
                    stage_code=t.stage,
                    doc_type=t.doc_type,
                    title=t.title,
                    required=t.required,
                    due_offset_days=t.due_offset_days,
                    condition=t.condition,
                    sort_order=order,
                )
            )
    await session.commit()


async def seed_checklists(session: AsyncSession) -> None:
    """Templates, then one checklist per package. Requires `seed_project` first."""
    await seed_checklist_templates(session)
    for package in (await session.execute(select(Package))).scalars().all():
        await instantiate_checklist(session, package)
    await session.commit()
