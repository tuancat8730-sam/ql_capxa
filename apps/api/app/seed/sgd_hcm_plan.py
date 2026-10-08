"""Baseline plan of the SGD-HCM project, copied from "Theo dõi tiến độ SGD-HCM.html".

That page keeps the plan (from "4.Kế hoạch tiến độ triển khai.xlsx") in its source and the
progress in a store this repository cannot read, so only the plan is seeded here.
"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class PlanTask:
    code: str  # "III-4" for a task, "M3" for a milestone
    name: str
    start: date
    end: date
    days: int  # working days, the weight of the task in the progress figures
    milestone: bool = False


@dataclass(frozen=True)
class PlanPhase:
    code: str
    name: str
    tasks: tuple[PlanTask, ...]


def _d(iso: str) -> date:
    return date.fromisoformat(iso)


PHASES: tuple[PlanPhase, ...] = (
    PlanPhase(
        "I",
        "Khởi động gói thầu",
        (
            PlanTask(
                "I-1",
                "Họp khởi động, thống nhất đầu mối và lập kế hoạch chi tiết",
                _d("2026-09-25"),
                _d("2026-09-29"),
                3,
            ),
        ),
    ),
    PlanPhase(
        "II",
        "Khảo sát, thu thập và phân tích yêu cầu",
        (
            PlanTask(
                "II-1",
                "Lập kế hoạch khảo sát và xác định đầu mối phối hợp",
                _d("2026-09-28"),
                _d("2026-09-30"),
                3,
            ),
            PlanTask(
                "II-2",
                "Khảo sát hiện trạng, phỏng vấn người dùng; thu thập tài liệu, biểu mẫu, dữ liệu và quy trình hiện có",
                _d("2026-10-01"),
                _d("2026-10-05"),
                3,
            ),
            PlanTask(
                "II-3",
                "Phân tích yêu cầu nghiệp vụ, chức năng, dữ liệu, phân quyền, tích hợp và phi chức năng",
                _d("2026-10-01"),
                _d("2026-10-06"),
                4,
            ),
            PlanTask(
                "II-4",
                "Rà soát, xác nhận danh mục yêu cầu; CĐT góp ý, phê duyệt hồ sơ khảo sát và tài liệu yêu cầu; hoàn thiện theo góp ý",
                _d("2026-10-06"),
                _d("2026-10-07"),
                2,
            ),
            PlanTask(
                "M1",
                "Hoàn thành khảo sát và xác nhận yêu cầu",
                _d("2026-10-07"),
                _d("2026-10-07"),
                0,
                milestone=True,
            ),
        ),
    ),
    PlanPhase(
        "III",
        "Thiết kế, xây dựng và tích hợp hệ thống",
        (
            PlanTask(
                "III-1",
                "Thiết kế kiến trúc, giao diện, chức năng, cơ sở dữ liệu, phân quyền, an toàn thông tin và hạ tầng triển khai",
                _d("2026-10-05"),
                _d("2026-10-09"),
                5,
            ),
            PlanTask(
                "III-2",
                "CĐT góp ý, phê duyệt hồ sơ thiết kế; hoàn thiện theo góp ý",
                _d("2026-10-12"),
                _d("2026-10-13"),
                2,
            ),
            PlanTask(
                "M2", "Phê duyệt thiết kế", _d("2026-10-13"), _d("2026-10-13"), 0, milestone=True
            ),
            PlanTask(
                "III-3",
                "Xây dựng các mô-đun nền tảng: Quản lý đơn vị, danh mục và dữ liệu dùng chung; Quản trị hệ thống, tài khoản, phân quyền, nhật ký, giám sát, sao lưu, khôi phục; Quản lý mã định danh",
                _d("2026-10-12"),
                _d("2026-11-03"),
                17,
            ),
            PlanTask(
                "III-4",
                "Xây dựng các mô-đun nghiệp vụ: Quản lý cơ sở vật chất, phòng học, phòng chức năng; Quản lý thiết bị (bàn giao, phân bổ, điều chuyển, mượn/trả); Quản lý kiểm kê; Quản lý bảo trì, sửa chữa; Quản lý nhu cầu và kế hoạch mua sắm",
                _d("2026-10-14"),
                _d("2026-11-03"),
                15,
            ),
            PlanTask(
                "III-5",
                "Xây dựng mô-đun Báo cáo, thống kê, bảng điều khiển, đánh giá hiệu quả sử dụng",
                _d("2026-10-16"),
                _d("2026-11-03"),
                13,
            ),
            PlanTask(
                "III-6",
                "Xây dựng API, kết nối và tích hợp với cơ sở dữ liệu ngành giáo dục và các hệ thống liên quan",
                _d("2026-10-15"),
                _d("2026-11-03"),
                14,
            ),
            PlanTask(
                "III-7",
                "CĐT góp ý phiên bản phần mềm và tài liệu tích hợp; hoàn thiện, kiểm tra nội bộ toàn bộ phiên bản phần mềm",
                _d("2026-11-05"),
                _d("2026-11-06"),
                2,
            ),
            PlanTask(
                "M3",
                "Hoàn thành phiên bản phần mềm và tích hợp phục vụ kiểm thử",
                _d("2026-11-06"),
                _d("2026-11-06"),
                0,
                milestone=True,
            ),
        ),
    ),
    PlanPhase(
        "IV",
        "Chuẩn hoá và chuyển đổi dữ liệu",
        (
            PlanTask(
                "IV-1", "Làm sạch, chuẩn hóa, ánh xạ dữ liệu", _d("2026-10-30"), _d("2026-11-02"), 2
            ),
            PlanTask(
                "IV-2",
                "Chuyển đổi thử nghiệm; nhập dữ liệu, đối soát và chuyển đổi chính thức",
                _d("2026-11-03"),
                _d("2026-11-04"),
                2,
            ),
            PlanTask(
                "IV-3",
                "CĐT góp ý, xác nhận kết quả chuyển đổi và đối soát dữ liệu; hoàn thiện báo cáo",
                _d("2026-11-05"),
                _d("2026-11-05"),
                1,
            ),
            PlanTask(
                "M4",
                "Hoàn thành chuyển đổi dữ liệu",
                _d("2026-11-05"),
                _d("2026-11-05"),
                0,
                milestone=True,
            ),
        ),
    ),
    PlanPhase(
        "V",
        "Kiểm thử và kiểm soát chất lượng (QA/QC) toàn hệ thống",
        (
            PlanTask(
                "V-1",
                "Lập kịch bản, kế hoạch kiểm thử và kiểm soát chất lượng; CĐT góp ý, xác nhận",
                _d("2026-10-07"),
                _d("2026-10-13"),
                5,
            ),
            PlanTask(
                "V-2",
                "Kiểm thử chức năng các mô-đun (cuốn chiếu theo tiến độ xây dựng); xử lý lỗi",
                _d("2026-10-15"),
                _d("2026-11-04"),
                15,
            ),
            PlanTask(
                "V-3",
                "CĐT góp ý báo cáo kết quả kiểm thử chức năng; hoàn thiện theo góp ý",
                _d("2026-11-05"),
                _d("2026-11-06"),
                2,
            ),
            PlanTask(
                "V-4",
                "Kiểm thử tích hợp, chuyển đổi dữ liệu, tương thích, hiệu năng và tải, bảo mật ATTT, phân quyền, sao lưu và khôi phục; kiểm thử hồi quy sau sửa lỗi",
                _d("2026-11-06"),
                _d("2026-11-09"),
                2,
            ),
            PlanTask(
                "V-5",
                "Kiểm thử chấp nhận của người sử dụng (UAT), CĐT góp ý; sửa lỗi, hoàn thiện và xác nhận biên bản UAT",
                _d("2026-11-10"),
                _d("2026-11-11"),
                2,
            ),
            PlanTask(
                "M5", "Hoàn thành kiểm thử", _d("2026-11-11"), _d("2026-11-11"), 0, milestone=True
            ),
        ),
    ),
    PlanPhase(
        "VI",
        "Triển khai phần mềm",
        (
            PlanTask("VI-1", "Chuẩn bị hạ tầng kỹ thuật", _d("2026-10-28"), _d("2026-10-30"), 3),
            PlanTask(
                "VI-2",
                "Cài đặt, cấu hình phần mềm; cấp tài khoản, phân quyền và đưa dữ liệu vào hệ thống",
                _d("2026-11-12"),
                _d("2026-11-13"),
                2,
            ),
        ),
    ),
    PlanPhase(
        "VII",
        "Đào tạo và chuyển giao",
        (
            PlanTask(
                "VII-1",
                "Biên soạn tài liệu đào tạo, hướng dẫn sử dụng; gửi người dùng xem trước khi đào tạo",
                _d("2026-11-05"),
                _d("2026-11-11"),
                5,
            ),
            PlanTask(
                "VII-2",
                "Đào tạo tại Sở: quản trị hệ thống, lãnh đạo Sở (buổi sáng); cán bộ các phòng, bộ phận thuộc Sở (buổi chiều)",
                _d("2026-11-16"),
                _d("2026-11-16"),
                1,
            ),
            PlanTask(
                "VII-3",
                "Đào tạo quản trị viên, cán bộ đầu mối và người sử dụng tại các đơn vị (trực tuyến hoặc tập trung); đánh giá kết quả đào tạo",
                _d("2026-11-17"),
                _d("2026-11-17"),
                1,
            ),
            PlanTask(
                "VII-4",
                "Chuyển giao hệ thống (phần mềm, mã nguồn/quyền sử dụng, quyền quản trị, API) và tài liệu; CĐT góp ý, xác nhận chuyển giao",
                _d("2026-11-18"),
                _d("2026-11-18"),
                1,
            ),
            PlanTask(
                "M6",
                "Hoàn thành đào tạo và chuyển giao",
                _d("2026-11-18"),
                _d("2026-11-18"),
                0,
                milestone=True,
            ),
        ),
    ),
    PlanPhase(
        "VIII",
        "Vận hành thử",
        (
            PlanTask(
                "VIII-1",
                "Lập, thống nhất kế hoạch vận hành thử với CĐT",
                _d("2026-11-19"),
                _d("2026-11-19"),
                1,
            ),
            PlanTask(
                "VIII-2",
                "Vận hành thử trên diện rộng; tiếp nhận phản hồi, xử lý lỗi, sự cố và kiểm thử lại",
                _d("2026-11-20"),
                _d("2026-11-24"),
                3,
            ),
            PlanTask("VIII-3", "Lập báo cáo vận hành thử", _d("2026-11-25"), _d("2026-11-25"), 1),
            PlanTask(
                "M7",
                "Hoàn thành vận hành thử",
                _d("2026-11-25"),
                _d("2026-11-25"),
                0,
                milestone=True,
            ),
        ),
    ),
    PlanPhase(
        "IX",
        "Nghiệm thu và bàn giao",
        (
            PlanTask(
                "IX-1",
                "Hoàn thiện hệ thống, cơ sở dữ liệu, hồ sơ nghiệm thu và tài liệu bàn giao",
                _d("2026-11-26"),
                _d("2026-11-26"),
                1,
            ),
            PlanTask(
                "IX-2",
                "CĐT góp ý, xác nhận nghiệm thu và bàn giao",
                _d("2026-11-27"),
                _d("2026-11-30"),
                2,
            ),
            PlanTask(
                "M8",
                "Nghiệm thu và bàn giao",
                _d("2026-11-30"),
                _d("2026-11-30"),
                0,
                milestone=True,
            ),
        ),
    ),
    PlanPhase(
        "X",
        "Hỗ trợ đưa vào vận hành chính thức",
        (
            PlanTask(
                "X-1",
                "Theo dõi, hỗ trợ người dùng và xử lý sự cố ban đầu; CĐT xác nhận vận hành chính thức",
                _d("2026-11-27"),
                _d("2026-11-30"),
                2,
            ),
        ),
    ),
    PlanPhase(
        "XI",
        "Thanh lý hợp đồng và giải ngân",
        (
            PlanTask(
                "XI-1",
                "Lập hồ sơ thanh lý hợp đồng và hồ sơ đề nghị thanh toán",
                _d("2026-11-24"),
                _d("2026-11-30"),
                5,
            ),
            PlanTask(
                "XI-2",
                "CĐT và nhà thầu thi công ký biên bản thanh lý hợp đồng",
                _d("2026-12-01"),
                _d("2026-12-01"),
                1,
            ),
            PlanTask(
                "XI-3",
                "CĐT gửi hồ sơ thanh toán; Kho bạc Nhà nước kiểm soát chi, giải ngân",
                _d("2026-12-01"),
                _d("2026-12-09"),
                7,
            ),
            PlanTask(
                "M9",
                "Hoàn thành thanh lý và giải ngân",
                _d("2026-12-09"),
                _d("2026-12-09"),
                0,
                milestone=True,
            ),
        ),
    ),
)
