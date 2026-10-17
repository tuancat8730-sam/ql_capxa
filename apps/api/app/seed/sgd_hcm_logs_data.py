"""SGD-HCM construction logs, copied from the contractor's weekly Word files.

Sources (data_documents/SGD_TPHCM/nhat_ky_thi_cong, git-ignored, hence copied here):
- Nhat_ky_thi_cong_tuan_01_(25092026-01102026).docx  -- reported 02/10/2026
- NTTC_Nhat ky thi cong tuan 03 (09102026-15102026).docx -- reported 16/10/2026
The log for 02/10 – 08/10/2026 (week 02) has not been supplied.

Notes on how the files were read:
- Phases follow the schedule (`sgd_hcm_plan`): the Word file numbers "Kiểm thử và kiểm soát chất
  lượng" as phase IV, the schedule as V.
- `task` is the schedule task a line is about. It is None where the file reports one line for
  several tasks ("Xây dựng hệ thống theo yêu cầu chức năng, nghiệp vụ…" spans III-3 to III-5).
- Saturday and Sunday carry "[....]" in the files: no line is written for them.
- A line's bullets stay in one text, one bullet per line; the "Nhân sự" column is a list of names.
"""

from typing import Any

# (date, phase, task, content, personnel, note, state, delay_days)
Entry = tuple[str, str, str | None, str, list[str], str | None, str | None, int | None]
# (phase, task, title, result to date, next week, note)
Carryover = tuple[str, str | None, str, str | None, str | None, str | None]

_BUILD = "Xây dựng hệ thống theo yêu cầu chức năng, nghiệp vụ trong hồ sơ gói thầu"
_SURVEY = (
    "Khảo sát hiện trạng, phỏng vấn người dùng; thu thập tài liệu, biểu mẫu, dữ liệu và quy "
    "trình hiện có"
)
_ANALYSIS = "Phân tích yêu cầu nghiệp vụ, chức năng, dữ liệu, phân quyền, tích hợp và phi chức năng"
_SURVEY_PLAN = "Lập kế hoạch khảo sát và xác định đầu mối phối hợp"
_REVIEW = (
    "Rà soát, xác nhận danh mục yêu cầu; CĐT góp ý, phê duyệt hồ sơ khảo sát và tài liệu yêu "
    "cầu; hoàn thiện theo góp ý"
)
_DESIGN = (
    "Thiết kế kiến trúc, giao diện, chức năng, cơ sở dữ liệu, phân quyền, an toàn thông tin và "
    "hạ tầng triển khai"
)
_DESIGN_REVIEW = "CĐT góp ý, phê duyệt hồ sơ thiết kế; hoàn thiện theo góp ý"
_API = (
    "Xây dựng API, kết nối và tích hợp với cơ sở dữ liệu ngành giáo dục và các hệ thống liên quan"
)
_TEST_PLAN = "Lập kịch bản, kế hoạch kiểm thử và kiểm soát chất lượng; CĐT góp ý, xác nhận"
_TEST_RUN = "Kiểm thử chức năng các mô-đun (cuốn chiếu theo tiến độ xây dựng); xử lý lỗi"
_ROLLING = "Đang thực hiện; kiểm thử nội bộ cuốn chiếu"
_DRAFT = "Dự thảo; chờ ký xác nhận từ CĐT"

_TEAM = ["Nguyễn Thành Tân", "Đỗ Thị Thu Hường"]

_RECIPIENTS = (
    "Sở Giáo dục và Đào tạo Thành phố Hồ Chí Minh (Chủ đầu tư); Đơn vị quản lý dự án; "
    "Đơn vị tư vấn giám sát"
)
_REPORTER = "Liên danh DVN (nhà thầu thi công)"
_CONTRACT = "Số 29/HĐKT-DVN ký ngày 21/9/2026"
_COORDINATOR = "Nguyễn Thị Thúy Hiệp"


def _bullets(*lines: str) -> str:
    return "\n".join(lines)


WEEK_01_ENTRIES: list[Entry] = [
    (
        "2026-09-25",
        "I",
        "I-1",
        "Họp khởi động, thống nhất đầu mối và lập kế hoạch chi tiết: hoàn thành buổi họp khởi động "
        "và thống nhất các đầu mối 4 bên: CĐT, Đơn vị QLDA, Đơn vị tư vấn giám sát, Nhà thầu thi "
        "công; nhà thầu thi công đã gửi lại kế hoạch chi tiết",
        [],
        "Cần xác nhận của CĐT về bản kế hoạch",
        "done",
        None,
    ),
    (
        "2026-09-25",
        "I",
        "I-1",
        "Biên bản họp khởi động có chữ ký xác nhận đại diện CĐT và nhà thầu: đã lập",
        [],
        "Đang rà soát",
        "in_progress",
        None,
    ),
    (
        "2026-09-25",
        "II",
        "II-3",
        f"{_ANALYSIS}: bắt đầu thực hiện",
        [],
        "Thực hiện sớm (kế hoạch 01/10 – 06/10), đang thực hiện",
        "in_progress",
        None,
    ),
    (
        "2026-09-25",
        "III",
        None,
        f"{_BUILD}: bắt đầu thực hiện",
        [],
        "Thực hiện sớm (kế hoạch 12/10 – 03/11), đang thực hiện",
        "in_progress",
        None,
    ),
    (
        "2026-09-28",
        "II",
        "II-1",
        f"{_SURVEY_PLAN}: bắt đầu thực hiện; Văn phòng Sở đã có văn bản ngày 30/9/2026 về cử nhân "
        "sự tham gia quản lý dự án",
        [],
        "Chậm 01 ngày do chưa có danh sách đầu mối tại các đơn vị",
        "in_progress",
        1,
    ),
    (
        "2026-09-29",
        "III",
        None,
        "Quản lý danh mục cơ quan quản lý và cơ sở giáo dục; Quản lý điểm trường: bắt đầu xây dựng",
        [],
        "Thực hiện sớm, đang thực hiện",
        "in_progress",
        None,
    ),
    (
        "2026-09-30",
        "III",
        None,
        "Hồ sơ công trình, khối nhà, phòng, khu vực: góp ý bổ sung lựa chọn phòng có được mượn hay "
        "không, danh sách thiết bị gắn cố định với phòng; ngày 01/10 bắt đầu xây dựng, kiểm thử "
        "nội bộ ghi nhận lỗi không lưu được thêm mới khối nhà, không thêm được phòng",
        [],
        "Thực hiện sớm, đang thực hiện, đang xử lý lỗi kiểm thử nội bộ",
        "in_progress",
        None,
    ),
    (
        "2026-10-01",
        "II",
        "II-2",
        f"{_SURVEY}: chưa bắt đầu",
        [],
        "Chưa bắt đầu do chưa có danh sách đầu mối, có thể bị chậm; triển khai ngay khi có đầu mối",
        "not_started",
        None,
    ),
    (
        "2026-10-01",
        "III",
        None,
        "Cập nhật danh mục thiết bị dạy học theo quy định: bắt đầu thực hiện; cập nhật danh mục "
        "thiết bị dạy học tối thiểu cấp Tiểu học, Trung học cơ sở, Trung học phổ thông theo Thông "
        "tư 37, 38, 39/2021/TT-BGDĐT; gộp màn hình chức năng Bộ tiêu chuẩn theo cấp và Định mức "
        "thiết bị theo cấp học, gộp màn hình chức năng trong danh mục dùng chung",
        [],
        "Thực hiện sớm, đang thực hiện",
        "in_progress",
        None,
    ),
    (
        "2026-10-01",
        "III",
        None,
        "Cấu trúc mã định danh thiết bị dạy học: đề xuất điều chỉnh so với quy tắc trong BCKTKT",
        [],
        "Chưa thực hiện",
        "not_started",
        None,
    ),
    (
        "2026-10-01",
        "III",
        None,
        "Danh mục phòng học, phòng bộ môn, phòng chức năng, khu vực sử dụng; Danh mục loại tài "
        "sản, nhóm thiết bị, môn học, mục đích sử dụng; Lịch sử sửa chữa, cải tạo, nâng cấp; Hồ "
        "sơ thiết bị; Nhập liệu thiết bị; Vị trí và người sử dụng; Cấu hình cấu trúc mã; Sinh mã "
        "và kiểm soát trùng; Quản lý vai trò và phân quyền; Đăng nhập và chính sách mật khẩu; "
        "Đăng nhập một lần (SSO): bắt đầu xây dựng",
        [],
        "Thực hiện sớm, đang thực hiện",
        "in_progress",
        None,
    ),
]

WEEK_01_CARRYOVERS: list[Carryover] = [
    (
        "I",
        "I-1",
        "Kế hoạch chi tiết",
        "Đã gửi, chờ CĐT xác nhận",
        "Tiếp nhận ý kiến, xác nhận của CĐT về bản kế hoạch chi tiết",
        "Cần xác nhận của CĐT về bản kế hoạch",
    ),
    (
        "I",
        "I-1",
        "Biên bản họp khởi động có chữ ký xác nhận đại diện CĐT và nhà thầu",
        "Đã lập, đang rà soát",
        "Hoàn thiện biên bản, lấy chữ ký xác nhận đại diện CĐT và nhà thầu",
        None,
    ),
    (
        "II",
        "II-1",
        _SURVEY_PLAN,
        "Chậm 01 ngày",
        _SURVEY_PLAN,
        "Đề nghị CĐT cung cấp danh sách đầu mối khảo sát sớm nhất để bảo đảm mốc hoàn thành khảo "
        "sát theo kế hoạch",
    ),
    (
        "II",
        "II-2",
        _SURVEY,
        "Chưa bắt đầu",
        f"{_SURVEY} (03 ngày làm việc từ khi có đầu mối)",
        "Kết quả dự kiến: biên bản làm việc; tài liệu, dữ liệu mẫu",
    ),
    (
        "II",
        "II-3",
        _ANALYSIS,
        "Triển khai sớm, từ 25/9",
        "Hoàn thiện phân tích yêu cầu (01/10 – 06/10)",
        "Hoàn thiện sau khảo sát",
    ),
    (
        "III",
        None,
        _BUILD,
        "Triển khai sớm, từ 25/9",
        "Tiếp tục xây dựng hệ thống (05/10 – 09/10)",
        "Kết quả dự kiến: các chức năng nền tảng",
    ),
]

WEEK_03_ENTRIES: list[Entry] = [
    (
        "2026-10-09",
        "I",
        "I-1",
        _bullets(
            "Sơ đồ tổ chức nhân sự thực hiện gói thầu",
            "- Cập nhật thông tin đầu mối các bên: đang thực hiện",
        ),
        ["Nguyễn Duy Khánh"],
        _DRAFT,
        "in_progress",
        None,
    ),
    (
        "2026-10-09",
        "II",
        "II-1",
        _bullets(
            _SURVEY_PLAN,
            "- Lập lại Kế hoạch khảo sát, danh sách đề xuất đơn vị khảo sát trực tiếp: đang thực "
            "hiện",
        ),
        ["Nguyễn Duy Khánh"],
        "Đang thực hiện, chậm tiến độ; chưa có đủ đầu mối tại các đơn vị",
        "in_progress",
        None,
    ),
    (
        "2026-10-09",
        "III",
        None,
        _bullets(
            _BUILD,
            "- Xử lý lỗi mã loại thiết bị (Nhập liệu thiết bị): đã xử lý",
            "- Điều chỉnh vị trí nhập Model, Hãng sản xuất vào chi tiết phiếu ghi tăng (Nhập liệu "
            "thiết bị): đang kiểm thử nội bộ",
            "- Xử lý mã môn học (Danh mục loại tài sản, nhóm thiết bị, môn học, mục đích sử dụng): "
            "đang kiểm thử nội bộ",
            "- Bổ sung thao tác thêm nhanh thông tin còn thiếu (Đối chiếu tiêu chuẩn, định mức): "
            "đang kiểm thử nội bộ",
            "- Xử lý trường bắt buộc trong phiếu (Báo hỏng, mất): đang kiểm thử nội bộ",
        ),
        _TEAM,
        _ROLLING,
        "in_progress",
        None,
    ),
    (
        "2026-10-12",
        "III",
        "III-2",
        _DESIGN_REVIEW,
        ["Nguyễn Thị Thúy Hiệp"],
        "Chưa bắt đầu; thực hiện sau khi có hồ sơ thiết kế",
        "not_started",
        None,
    ),
    (
        "2026-10-12",
        "III",
        None,
        _bullets(
            _BUILD,
            "- Điều chỉnh phiếu ghi tăng theo kết quả kiểm thử nội bộ (nguồn hình thành, nguồn kinh "
            "phí, nơi nhận, thêm thiết bị, tệp đính kèm, kiểm tra đơn giá; Model, Hãng sản xuất): "
            "đã hoàn thành",
            "- Xử lý trường bắt buộc trong phiếu (Báo hỏng, mất): đã xử lý",
            "- Xử lý mã môn học (Danh mục loại tài sản, nhóm thiết bị, môn học, mục đích sử dụng): "
            "đang điều chỉnh theo kết quả kiểm thử nội bộ",
            "- Cấu hình quy tắc điều chỉnh danh mục thiết bị dạy học tối thiểu: bắt đầu thực hiện",
        ),
        _TEAM,
        _ROLLING,
        "in_progress",
        None,
    ),
    (
        "2026-10-13",
        "III",
        None,
        _bullets(
            _BUILD,
            "- Xử lý mã môn học (Danh mục loại tài sản, nhóm thiết bị, môn học, mục đích sử dụng): "
            "đã xử lý",
            "- Xử lý quyền xem phiếu lưu nháp của Hiệu trưởng (Ghi tăng thiết bị): đã xử lý",
            "- Xử lý trạng thái phiếu sau khi trình duyệt (Ghi tăng thiết bị): đang kiểm thử nội bộ",
            "- Điều chỉnh chức năng nộp phiếu (Báo hỏng, mất): đang kiểm thử nội bộ",
            "- Bổ sung nguồn chi dự kiến (Báo hỏng, mất): đang thực hiện",
        ),
        _TEAM,
        _ROLLING,
        "in_progress",
        None,
    ),
    (
        "2026-10-14",
        "II",
        "II-1",
        _bullets(
            _SURVEY_PLAN,
            "- Gửi CĐT Kế hoạch khảo sát, danh sách đề xuất đơn vị khảo sát trực tiếp và các biểu "
            "mẫu: đã gửi ngày 14/10",
            "- Tiếp nhận đầu mối của CĐT hỗ trợ kỹ thuật, chuyên môn phần mềm (Mr.Khoa): đã tiếp "
            "nhận",
        ),
        ["Nguyễn Thị Thúy Hiệp"],
        "Chậm tiến độ; đã gửi CĐT ngày 14/10; chờ thống nhất danh sách đơn vị, đầu mối phối hợp",
        "in_progress",
        None,
    ),
    (
        "2026-10-15",
        "I",
        "I-1",
        "Biên bản họp khởi động; văn bản thông qua Kế hoạch tiến độ triển khai",
        ["Nguyễn Duy Khánh"],
        _DRAFT,
        "in_progress",
        None,
    ),
    (
        "2026-10-15",
        "II",
        "II-2",
        _bullets(
            _SURVEY,
            "- Lập hồ sơ đề xuất điều chỉnh mốc hoàn thành khảo sát và biện pháp bù tiến độ: đã "
            "lập, chờ trình phê duyệt",
        ),
        ["Nguyễn Thị Thúy Hiệp"],
        "Chậm 08 ngày; triển khai khi có đầu mối phối hợp",
        "not_started",
        8,
    ),
    (
        "2026-10-15",
        "II",
        "II-3",
        _ANALYSIS,
        ["Nguyễn Đình Đạt"],
        "Đang thực hiện; hoàn thiện sau khảo sát",
        "in_progress",
        None,
    ),
    (
        "2026-10-15",
        "II",
        "II-4",
        _REVIEW,
        ["Nguyễn Thị Thúy Hiệp"],
        "Chậm 06 ngày; thực hiện sau khi hoàn thành khảo sát",
        "not_started",
        6,
    ),
    (
        "2026-10-15",
        "III",
        "III-1",
        _DESIGN,
        ["Nguyễn Đình Đạt"],
        "Đang thực hiện; đang hoàn thiện hồ sơ thiết kế",
        "in_progress",
        None,
    ),
    (
        "2026-10-15",
        "III",
        None,
        _bullets(
            _BUILD,
            "- Hồ sơ công trình, khối nhà, phòng, khu vực: đã hoàn thành kiểm thử nội bộ",
            "- Quản lý danh mục cơ quan quản lý và cơ sở giáo dục; Quản lý điểm trường: đã hoàn "
            "thành kiểm thử nội bộ",
            "- Xử lý trạng thái phiếu sau khi trình duyệt, khi bị trả về (Ghi tăng thiết bị): đã "
            "xử lý",
            "- Điều chỉnh chức năng nộp phiếu (Báo hỏng, mất): đang điều chỉnh theo kết quả kiểm "
            "thử nội bộ",
            "- Dựng mẫu giao diện cấu hình quy tắc điều chỉnh tự động và điều chỉnh theo đề xuất "
            "của trường: đang thực hiện",
            "- Lập đề nghị thay đổi cấu trúc mã định danh thiết bị (Mô-đun Quản lý mã định danh): "
            "đã lập, chờ trình phê duyệt",
        ),
        [*_TEAM, "Đỗ Ngọc Khánh", "Nguyễn Thị Thúy Hiệp"],
        _ROLLING,
        "in_progress",
        None,
    ),
    (
        "2026-10-15",
        "III",
        "III-6",
        _API,
        ["Nguyễn Thành Tân", "Nguyễn Đình Đạt"],
        "Đang thực hiện; theo kế hoạch từ 15/10",
        "in_progress",
        None,
    ),
    (
        "2026-10-15",
        "V",
        "V-1",
        _TEST_PLAN,
        ["Đỗ Thị Thu Hường"],
        "Chậm 02 ngày",
        None,
        2,
    ),
    (
        "2026-10-15",
        "V",
        "V-2",
        _TEST_RUN,
        ["Đỗ Thị Thu Hường"],
        "Chưa bắt đầu; thực hiện sau khi có kịch bản kiểm thử",
        "not_started",
        None,
    ),
]

WEEK_03_CARRYOVERS: list[Carryover] = [
    (
        "I",
        "I-1",
        "Sơ đồ tổ chức nhân sự thực hiện gói thầu",
        _DRAFT,
        "Ký xác nhận cùng Biên bản họp khởi động khi có đủ đầu mối",
        None,
    ),
    (
        "I",
        "I-1",
        "Biên bản họp khởi động; văn bản thông qua Kế hoạch tiến độ triển khai",
        _DRAFT,
        "Trình ký cùng Kế hoạch khảo sát khi có đủ đầu mối",
        None,
    ),
    (
        "II",
        "II-1",
        _SURVEY_PLAN,
        "Chậm 11 ngày; đã gửi CĐT ngày 14/10; chờ thống nhất danh sách đơn vị, đầu mối",
        "Trình CĐT hồ sơ đề xuất điều chỉnh mốc hoàn thành khảo sát và biện pháp bù tiến độ (theo "
        "lịch họp thống nhất)",
        None,
    ),
    (
        "II",
        "II-2",
        _SURVEY,
        "Chậm 08 ngày",
        "Phối hợp triển khai khảo sát tại các đơn vị theo danh sách được thống nhất (theo lịch "
        "phối hợp)",
        "Kết quả dự kiến: biên bản làm việc; tài liệu, dữ liệu mẫu",
    ),
    (
        "II",
        "II-3",
        _ANALYSIS,
        "Đang thực hiện, từ 25/9",
        "Hoàn thiện phân tích yêu cầu sau khảo sát",
        None,
    ),
    (
        "II",
        "II-4",
        _REVIEW,
        "Chậm 06 ngày",
        "Thực hiện sau khi hoàn thành khảo sát",
        None,
    ),
    (
        "III",
        "III-1",
        _DESIGN,
        "Đang thực hiện, từ 05/10",
        "Hoàn thiện hồ sơ thiết kế hệ thống (19/10 – 23/10)",
        "Kết quả dự kiến: hồ sơ thiết kế (dự thảo)",
    ),
    (
        "III",
        "III-2",
        _DESIGN_REVIEW,
        "Chưa bắt đầu; có thể bị chậm",
        "Thực hiện sau khi có hồ sơ thiết kế",
        None,
    ),
    (
        "III",
        None,
        _BUILD,
        "Đang thực hiện, từ 25/9",
        "Tiếp tục xây dựng, kiểm thử nội bộ cuốn chiếu các mô-đun nền tảng và nghiệp vụ (19/10 – "
        "23/10); trình CĐT đề nghị thay đổi cấu trúc mã định danh thiết bị (19/10 – 23/10)",
        "Đến 03/11",
    ),
    (
        "III",
        "III-6",
        _API,
        "Đang thực hiện, từ 15/10",
        "Tiếp tục xây dựng các chức năng kết nối, tích hợp (19/10 – 23/10)",
        "Đến 03/11",
    ),
    (
        "V",
        "V-1",
        _TEST_PLAN,
        "Chậm 02 ngày",
        "Lập kịch bản, kế hoạch kiểm thử và kiểm soát chất lượng (19/10 – 23/10)",
        "Kết quả dự kiến: kế hoạch kiểm thử (dự thảo)",
    ),
    (
        "V",
        "V-2",
        _TEST_RUN,
        "Chưa bắt đầu",
        "Thực hiện sau khi có kịch bản kiểm thử",
        "Đến 04/11",
    ),
]

LOGS: list[dict[str, Any]] = [
    {
        "week_start": "2026-09-25",
        "report_date": "2026-10-02",
        "recipients": _RECIPIENTS,
        "reporter_org": _REPORTER,
        "contract_ref": _CONTRACT,
        "coordinator": _COORDINATOR,
        "environment_note": None,
        "overall_status": "Nhà thầu đang bám sát đúng tiến độ; giai đoạn khảo sát có thể lùi lại do "
        "cần có danh sách đầu mối tại các đơn vị để phối hợp khảo sát.",
        "key_results": "Đang phân tích yêu cầu và triển khai sớm việc xây dựng hệ thống theo yêu "
        "cầu chức năng, nghiệp vụ trong hồ sơ gói thầu.",
        "issues": _bullets(
            "Chưa có đầu mối tại các đơn vị để phối hợp khảo sát; thu thập tài liệu, biểu mẫu.",
            "Ảnh hưởng: chậm tiến độ của mốc hoàn thành khảo sát, phân tích nghiệp vụ, thu thập "
            "biểu mẫu, tài liệu.",
            "Phương án xử lý: đề xuất CĐT hỗ trợ gửi công văn đề nghị đơn vị phối hợp.",
        ),
        "coordination_requests": _bullets(
            "- Ban hành Kế hoạch phối hợp khảo sát (CĐT).",
            "- Cử nhân sự tham gia quản lý dự án (tham gia ý kiến về nghiệp vụ, chuyên môn) (Phòng "
            "Kế hoạch - Tài chính): Văn phòng Sở đã có văn bản ngày 30/9/2026.",
            "- Quyết định danh sách trường; cử đầu mối khảo sát tại các phòng, bộ phận và từng "
            "trường (CĐT; các trường).",
            "- Đề nghị UBND xã/phường cử cán bộ phối hợp (CĐT).",
            "- Cung cấp tài liệu, biểu mẫu, dữ liệu mẫu, quy trình hiện có (Các đơn vị khảo sát).",
        ),
        "related_report": "Báo cáo tiến độ dự án tuần (25/9 – 01/10/2026) ngày 02/10/2026",
        "entries": WEEK_01_ENTRIES,
        "carryovers": WEEK_01_CARRYOVERS,
        "member_work": [],
    },
    {
        "week_start": "2026-10-09",
        "report_date": "2026-10-16",
        "recipients": _RECIPIENTS,
        "reporter_org": _REPORTER,
        "contract_ref": _CONTRACT,
        "coordinator": _COORDINATOR,
        "environment_note": "Môi trường phát triển, kiểm thử nội bộ của nhà thầu thi công; chưa phát "
        "hành phiên bản bàn giao kiểm tra",
        "overall_status": "Nhà thầu đang bám sát tiến độ xây dựng hệ thống; đã gửi CĐT Kế hoạch "
        "khảo sát, danh sách đề xuất đơn vị khảo sát và các biểu mẫu ngày 14/10/2026; giai đoạn "
        "khảo sát có thể lùi lại do cần thống nhất danh sách đơn vị và đầu mối phối hợp.",
        "key_results": "Tiếp tục thiết kế, xây dựng và kiểm thử nội bộ cuốn chiếu; đã hoàn thành "
        "Quản lý danh mục cơ quan quản lý và cơ sở giáo dục, Quản lý điểm trường, Hồ sơ công "
        "trình, khối nhà, phòng, khu vực.",
        "issues": _bullets(
            f"- {_SURVEY_PLAN}: chậm tiến độ công việc khảo sát; phương án xử lý: nhà thầu đã gửi "
            "CĐT Kế hoạch khảo sát, danh sách đề xuất đơn vị khảo sát ngày 14/10/2026; CĐT thống "
            "nhất danh sách, đầu mối phối hợp (CĐT; đang thực hiện).",
            f"- {_SURVEY}: chậm tiến độ công việc khảo sát; phương án xử lý: lập hồ sơ đề xuất "
            "điều chỉnh mốc hoàn thành khảo sát và biện pháp bù tiến độ, trình CĐT (nhà thầu thi "
            "công; đang thực hiện).",
            "- Quy tắc mã định danh thiết bị trong Báo cáo kinh tế - kỹ thuật dành 02 ký tự cho số "
            "thứ tự thiết bị, không đủ khi số thiết bị lớn hơn 99: ảnh hưởng chức năng sinh mã "
            "định danh thiết bị; phương án xử lý: đề xuất tăng số thứ tự thiết bị lên 04 ký tự, "
            "lập đề nghị thay đổi trình CĐT xem xét (nhà thầu thi công; CĐT; đang thực hiện).",
        ),
        "coordination_requests": _bullets(
            "- Ban hành Kế hoạch phối hợp khảo sát (CĐT): nhà thầu đã gửi Kế hoạch khảo sát ngày "
            "14/10/2026.",
            "- Quyết định danh sách trường; cử đầu mối khảo sát từng trường (CĐT; các trường): "
            "nhà thầu đã gửi danh sách đề xuất ngày 14/10/2026.",
            "- Đề nghị Ủy ban nhân dân xã/phường cử cán bộ phối hợp (CĐT).",
            "- Cung cấp tài liệu, biểu mẫu, dữ liệu mẫu, quy trình hiện có (Các đơn vị khảo sát).",
            "- Ký Biên bản họp khởi động, văn bản thông qua Kế hoạch tiến độ triển khai, Kế hoạch "
            "khảo sát, ký một lần khi đủ đầu mối (CĐT; nhà thầu thi công).",
            "- Xem xét hồ sơ đề xuất điều chỉnh mốc hoàn thành khảo sát (CĐT).",
            "- Xem xét đề nghị thay đổi cấu trúc mã định danh thiết bị (CĐT).",
        ),
        "related_report": "Báo cáo tiến độ dự án tuần (09/10 – 15/10/2026) ngày 16/10/2026",
        "entries": WEEK_03_ENTRIES,
        "carryovers": WEEK_03_CARRYOVERS,
        "member_work": [
            {
                "member_name": "VietFuture",
                "item": "Mô-đun Quản lý mã định danh",
                "plan_ref": "Đối chiếu KH chi tiết: 5.4 – Mô-đun Quản lý mã định danh; 7.2 – Xây "
                "dựng, cấu hình và hoàn thiện mô-đun Quản lý mã định danh",
                "personnel": [
                    "Đỗ Ngọc Khánh – Chuyên gia phát triển phần mềm (xây dựng, cấu hình, hoàn "
                    "thiện mô-đun)"
                ],
                "result": _bullets(
                    "- Cấu hình cấu trúc mã: đang thực hiện",
                    "- Sinh mã và kiểm soát trùng; Tra cứu theo mã; Mã vạch, mã QR; Truy vết vòng "
                    "đời: đang kiểm thử nội bộ",
                    "- Lập đề nghị thay đổi cấu trúc mã định danh thiết bị: đã lập ngày 15/10, "
                    "chờ trình phê duyệt",
                ),
                "next_plan": _bullets(
                    "- Tiếp tục xây dựng, kiểm thử nội bộ cuốn chiếu các chức năng của mô-đun "
                    "(đến 03/11)",
                    "- Trình CĐT đề nghị thay đổi cấu trúc mã định danh thiết bị (19/10 – 23/10)",
                ),
                "issues_actions": _bullets(
                    "- Vướng mắc: Quy tắc mã trong Báo cáo kinh tế - kỹ thuật "
                    "(TT.TR.MH.LT.ST.NC) dành 02 ký tự cho số thứ tự thiết bị, không đủ khi số "
                    "thiết bị lớn hơn 99.",
                    "- Biện pháp: nhà thầu thi công đã đề xuất tăng số thứ tự thiết bị lên 04 ký "
                    "tự (XX.XX.XX.XX.XXXX.XX) ngày 01/10; đang điều chỉnh trên hệ thống; đã lập "
                    "đề nghị thay đổi, chờ trình CĐT phê duyệt.",
                ),
            },
            {
                "member_name": "VietFuture",
                "item": "Phân tích, thiết kế, tích hợp và chuyển đổi dữ liệu",
                "plan_ref": "Đối chiếu KH chi tiết: 2.4, 3.2 – Phối hợp khảo sát, phân tích yêu "
                "cầu của mô-đun; 4.3 – Phối hợp thiết kế chi tiết mô-đun; 7.4 – Phối hợp tích "
                "hợp mô-đun vào hệ thống chung; 6.2 – Phối hợp chuẩn hóa, ánh xạ, chuyển đổi và "
                "đối soát dữ liệu mã định danh",
                "personnel": [
                    "Nguyễn Đình Đạt – Chuyên gia phân tích, thiết kế hệ thống và tích hợp dữ "
                    "liệu (phối hợp phân tích, thiết kế chi tiết, tích hợp mô-đun)",
                    "Nguyễn Ngọc Ninh – Chuyên gia triển khai, chuyển đổi dữ liệu, đào tạo và "
                    "chuyển giao (phối hợp chuyển đổi, đối soát dữ liệu mã định danh)",
                ],
                "result": _bullets(
                    "- Phối hợp phân tích yêu cầu của mô-đun: đang thực hiện; hoàn thiện sau khảo "
                    "sát",
                    "- Phối hợp thiết kế chi tiết mô-đun: đang thực hiện cùng đầu việc thiết kế "
                    "hệ thống",
                    "- Phối hợp tích hợp mô-đun vào hệ thống chung: đến kỳ thực hiện (kế hoạch từ "
                    "15/10)",
                    "- Chuyển đổi, đối soát dữ liệu mã định danh: chưa đến kỳ (kế hoạch từ 30/10)",
                ),
                "next_plan": _bullets(
                    "- Phối hợp hoàn thiện thiết kế chi tiết mô-đun (19/10 – 23/10)",
                    "- Phối hợp tích hợp mô-đun vào hệ thống chung (đến 03/11)",
                    "- Phối hợp hoàn thiện phân tích yêu cầu của mô-đun sau khảo sát",
                ),
                "issues_actions": None,
            },
        ],
    },
]
