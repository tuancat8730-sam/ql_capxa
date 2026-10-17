"""SGD-HCM progress data as exported from the tracking page on 17/10/2026.

Generated from data_documents/SGD_TPHCM/data_updated_20261017.md (up to the contractor's
report for 09/10 – 15/10/2026, received 16/10/2026). Applied by migration 0015 to an existing
database and by the seed to a new one.
"""

from typing import Any

# (task code, status, pct, actual start, actual end, note) -- ISO dates
TASKS: list[tuple[str, str, int, str | None, str | None, str | None]] = [
    (
        "I-1",
        "done",
        100,
        "2026-09-25",
        "2026-09-29",
        "Đã họp khởi động 4 bên (BC tuần 25/9–01/10 của nhà thầu).",
    ),
    (
        "II-1",
        "in_progress",
        0,
        "2026-09-28",
        None,
        "Chậm 11 ngày. Ngày 14/10 đã gửi CĐT Kế hoạch khảo sát, danh sách đề xuất đơn vị khảo sát trực "
        "tiếp và biểu mẫu khảo sát; CĐT cử Mr. Khoa làm đầu mối hỗ trợ kỹ thuật, chuyên môn phần mềm; "
        "CĐT còn phải thống nhất danh sách đơn vị và đầu mối phối hợp (BC nhà thầu 09/10–15/10, nộp "
        "16/10). Báo cáo không nêu % — chưa tính tiến độ.",
    ),
    (
        "II-2",
        "not_started",
        0,
        None,
        None,
        "Chậm 08 ngày; triển khai khi có đầu mối (BC nhà thầu 09/10–15/10, nộp 16/10). Báo cáo không nêu "
        "% — chưa tính tiến độ.",
    ),
    (
        "II-3",
        "in_progress",
        0,
        "2026-09-25",
        None,
        "Đang thực hiện, hoàn thiện sau khảo sát (BC nhà thầu 09/10–15/10, nộp 16/10). Báo cáo không nêu "
        "% — chưa tính tiến độ.",
    ),
    (
        "II-4",
        "not_started",
        0,
        None,
        None,
        "Chậm 06 ngày; làm sau khi hoàn thành khảo sát (BC nhà thầu 09/10–15/10, nộp 16/10). Báo cáo "
        "không nêu % — chưa tính tiến độ.",
    ),
    (
        "III-1",
        "in_progress",
        0,
        "2026-10-05",
        None,
        "Đang hoàn thiện hồ sơ thiết kế (kế hoạch kết thúc 09/10); hồ sơ thiết kế dự thảo dự kiến "
        "19/10–23/10 (BC nhà thầu 09/10–15/10, nộp 16/10). Báo cáo không nêu % — chưa tính tiến độ.",
    ),
    (
        "III-2",
        "not_started",
        0,
        None,
        None,
        "Có thể bị chậm (kế hoạch 12–13/10); làm sau khi có hồ sơ thiết kế (BC nhà thầu 09/10–15/10, nộp "
        "16/10). Báo cáo không nêu % — chưa tính tiến độ.",
    ),
    (
        "III-3",
        "in_progress",
        0,
        "2026-09-25",
        None,
        "Kiểm thử nội bộ cuốn chiếu. Đã hoàn thành: Quản lý danh mục cơ quan quản lý và cơ sở giáo dục; "
        "Quản lý điểm trường. Báo cáo ghi chung một mục 'xây dựng hệ thống' (kế hoạch 12/10–03/11) (BC "
        "nhà thầu 09/10–15/10, nộp 16/10). Báo cáo không nêu % — chưa tính tiến độ.",
    ),
    (
        "III-4",
        "in_progress",
        0,
        "2026-09-25",
        None,
        "Đã hoàn thành Hồ sơ công trình, khối nhà, phòng, khu vực. Báo cáo ghi chung một mục 'xây dựng "
        "hệ thống' (kế hoạch 12/10–03/11) (BC nhà thầu 09/10–15/10, nộp 16/10). Báo cáo không nêu % — "
        "chưa tính tiến độ.",
    ),
    (
        "III-6",
        "in_progress",
        0,
        "2026-10-15",
        None,
        "Bắt đầu từ 15/10 theo kế hoạch (BC nhà thầu 09/10–15/10, nộp 16/10). Báo cáo không nêu % — chưa "
        "tính tiến độ.",
    ),
    (
        "V-1",
        "not_started",
        0,
        None,
        None,
        "Chậm 02 ngày; kế hoạch kiểm thử (dự thảo) dự kiến 19/10–23/10; đề xuất kế hoạch và phương thức "
        "kiểm thử, nghiệm thu đang lập (BC nhà thầu 09/10–15/10, nộp 16/10). Báo cáo không nêu % — chưa "
        "tính tiến độ.",
    ),
    (
        "V-2",
        "not_started",
        0,
        None,
        None,
        "Kế hoạch 15/10–04/11; làm sau khi có kịch bản kiểm thử (BC nhà thầu 09/10–15/10, nộp 16/10). "
        "Báo cáo không nêu % — chưa tính tiến độ.",
    ),
    (
        "M1",
        "not_started",
        0,
        None,
        None,
        "Chưa đạt: mốc 07/10 không đạt, chưa có ngày mới. Nhà thầu đã lập hồ sơ đề xuất điều chỉnh mốc "
        "hoàn thành khảo sát và biện pháp bù tiến độ, chờ trình CĐT (19/10–23/10) (BC nhà thầu "
        "09/10–15/10, nộp 16/10)",
    ),
    (
        "M2",
        "not_started",
        0,
        None,
        None,
        "Chưa đạt mốc phê duyệt thiết kế 13/10: hồ sơ thiết kế còn đang lập, CĐT chưa phê duyệt (BC nhà "
        "thầu 09/10–15/10, nộp 16/10)",
    ),
]

REPORTS: list[dict[str, Any]] = [
    {
        "actual_pct": 2,
        "done": "Họp khởi động 4 bên hoàn thành (25–29/9). Triển khai sớm phân tích yêu cầu và xây dựng "
        "hệ thống từ 25/9. Lập kế hoạch khảo sát và xác định đầu mối bắt đầu từ 28/9, chậm 01 "
        "ngày. Nhà thầu nhận định bám sát tiến độ.",
        "issues": "Chưa có đầu mối tại các đơn vị để phối hợp khảo sát, thu thập tài liệu, biểu mẫu. Sở "
        "đã gửi công văn đề xuất đầu mối đến Chánh Văn phòng Sở nhưng chưa có phản hồi. Khảo "
        "sát hiện trạng có thể bị chậm, ảnh hưởng mốc M1 (07/10).",
        "link": "https://drive.google.com/file/d/1OXQagcHBJ6hYa_lqzaIJuO9vWY6-hRv-/view?usp=drivesdk",
        "next_plan": "05/10–09/10: khảo sát hiện trạng (3 ngày làm việc từ khi có đầu mối); hoàn thiện "
        "phân tích yêu cầu, CĐT xác nhận 06–07/10; thiết kế dự thảo 05–09/10; tiếp tục xây "
        "dựng nền tảng. Theo giao ban 02/10: DTH đề xuất danh sách trường đầu mối + UBND "
        "phường, gửi Thuyết minh kỹ thuật và kế hoạch Kiểm thử – Nghiệm thu trong tuần tới; "
        "báo cáo tuần nộp trước 8h00 thứ Sáu.",
        "planned_pct": 5,
        "recommendations": "Đề nghị CĐT ban hành Kế hoạch phối hợp khảo sát, quyết định danh sách trường "
        "và cử đầu mối khảo sát; đề nghị UBND xã/phường cử cán bộ phối hợp; cung cấp "
        "danh sách đầu mối sớm nhất.",
        "report_no": "BC-01",
        "risks": ["PM-01", "PM-02", "PM-13"],
        "submitted_on": "2026-10-02",
        "week_start": "2026-09-25",
    },
    {
        "actual_pct": 2,
        "done": "Đã có đầu mối Phòng KH-TC và Phòng GD Mầm non; nhà thầu đề xuất CĐT 02 đơn vị THPT (dự "
        "thảo công văn gửi 07/10). Gửi 03 tài liệu ngày 07/10 (thuyết minh kỹ thuật, danh mục "
        "chức năng, phương án chuẩn hóa dữ liệu). Thiết kế hệ thống từ 05/10; xây dựng sớm từ "
        "25/9, kiểm thử nội bộ cuốn chiếu. Crystal (CRY-SGD-WR-02): tình trạng CHẬM, cần CĐT can "
        "thiệp.",
        "issues": "Lập kế hoạch khảo sát chậm 05 ngày; khảo sát hiện trạng chậm 02–05 ngày, chưa khảo "
        "sát trực tiếp tại đơn vị/trường nào; mốc H2 (M1) 07/10 không đạt, chưa có ngày mới. "
        "Phạm vi và danh sách trường khảo sát chưa được CĐT xác nhận. Biên bản họp khởi động "
        "và văn bản thông qua kế hoạch tiến độ chưa ký (H0 chưa khóa). Mô-đun mã định danh "
        "(VietFuture) không có trong báo cáo nhà thầu. Đề xuất kế hoạch kiểm thử, nghiệm thu "
        "chưa gửi.",
        "link": "https://drive.google.com/file/d/1NZSwKdYE2I1tw5iM9hYZ-yR3yKutJH0J/view?usp=drivesdk",
        "next_plan": "08/10–16/10: họp sơ bộ Phòng KH-TC (09/10), khảo sát tại Phòng GD Mầm non và các "
        "trường (03 ngày làm việc từ khi có đầu mối); gửi CĐT dự thảo văn bản thông qua kế "
        "hoạch tiến độ và hoàn thiện thiết kế (09/10); lập kế hoạch kiểm thử (08–13/10); "
        "tiếp tục xây dựng. Mốc phê duyệt thiết kế 13/10. Crystal: góp ý biểu mẫu khảo sát, "
        "chứng kiến ≥1 buổi khảo sát, rà soát thiết kế dự thảo. Họp tại Sở GD&ĐT 9h00 thứ "
        "Sáu 16/10.",
        "planned_pct": 14,
        "recommendations": "CĐT: xác nhận bằng văn bản danh sách trường khảo sát và tính đại diện cho "
        "hơn 2.000 trường, ban hành biểu mẫu khảo sát kèm công văn (trước hoặc tại "
        "họp 9h00 thứ Sáu 16/10); ban hành công văn 02 trường THPT, Kế hoạch phối hợp "
        "khảo sát, đề nghị UBND xã/phường cử cán bộ; ký biên bản họp khởi động và văn "
        "bản thông qua kế hoạch tiến độ; cung cấp QĐ phê duyệt kết quả lựa chọn nhà "
        "thầu (PL-02).",
        "report_no": "BC-02",
        "risks": ["PM-01", "PM-02", "PM-03", "PM-13", "PM-14", "PM-15"],
        "submitted_on": "2026-10-08",
        "week_start": "2026-10-02",
    },
    {
        "actual_pct": 2,
        "done": "Ngày 14/10 gửi CĐT Kế hoạch khảo sát, danh sách đề xuất đơn vị khảo sát trực tiếp và "
        "biểu mẫu khảo sát; CĐT cử Mr. Khoa làm đầu mối hỗ trợ kỹ thuật, chuyên môn phần mềm. "
        "Hoàn thành mô-đun Quản lý danh mục cơ quan quản lý và cơ sở giáo dục, Quản lý điểm "
        "trường, Hồ sơ công trình, khối nhà, phòng, khu vực. Tiếp tục thiết kế (đang hoàn thiện "
        "hồ sơ), xây dựng, kiểm thử nội bộ cuốn chiếu; bắt đầu xây dựng API, tích hợp từ 15/10. "
        "Đã lập đề nghị thay đổi cấu trúc mã định danh và hồ sơ đề xuất điều chỉnh mốc hoàn "
        "thành khảo sát (chờ trình).",
        "issues": "Chậm: lập kế hoạch khảo sát 11 ngày, khảo sát hiện trạng 08 ngày (chưa bắt đầu), xác "
        "nhận yêu cầu 06 ngày, lập kế hoạch kiểm thử 02 ngày; phê duyệt thiết kế (13/10) chưa "
        "thực hiện vì chưa có hồ sơ thiết kế. Danh sách đơn vị khảo sát và đầu mối phối hợp "
        "chưa được CĐT thống nhất. Quy tắc mã định danh trong Báo cáo KT-KT chỉ có 02 ký tự "
        "cho số thứ tự thiết bị, không đủ khi hơn 99 thiết bị. Sơ đồ nhân sự, biên bản họp "
        "khởi động, văn bản thông qua kế hoạch tiến độ còn dự thảo chờ ký.",
        "link": "https://drive.google.com/file/d/1PoaOJrBhcyx7VW4RJsYL40GzEjPNCXzX/view?usp=drivesdk",
        "next_plan": "19/10–23/10: trình CĐT hồ sơ đề xuất điều chỉnh mốc khảo sát và biện pháp bù tiến "
        "độ; phối hợp khảo sát theo danh sách được thống nhất; trình đề nghị thay đổi cấu "
        "trúc mã định danh; hoàn thiện phân tích yêu cầu sau khảo sát; hoàn thiện hồ sơ "
        "thiết kế (dự thảo) và kế hoạch kiểm thử (dự thảo); tiếp tục xây dựng, kiểm thử nội "
        "bộ, API và tích hợp.",
        "planned_pct": 22,
        "recommendations": "Đề nghị CĐT sớm thống nhất danh sách đơn vị khảo sát và đầu mối phối hợp; "
        "xem xét hồ sơ đề xuất điều chỉnh mốc hoàn thành khảo sát và đề nghị thay đổi "
        "cấu trúc mã định danh (tăng số thứ tự lên 04 ký tự); ban hành Kế hoạch phối "
        "hợp khảo sát, đề nghị UBND xã/phường cử cán bộ; ký các văn bản đang chờ.",
        "report_no": "BC-03",
        "risks": ["PM-02", "PM-06", "PM-13", "PM-14", "PM-16"],
        "submitted_on": "2026-10-16",
        "week_start": "2026-10-09",
    },
]

RISKS: list[dict[str, Any]] = [
    {
        "code": "PM-01",
        "due_date": None,
        "group_name": "Dữ liệu",
        "impact": 5,
        "mitigation": "Yêu cầu LD DVN công bố kế hoạch thu thập dữ liệu chi tiết theo từng đơn vị, có cơ "
        "chế cảnh báo sớm khi đơn vị chậm nộp (tại họp khởi động). Liên hệ Crystal R01.",
        "note": "02/10: chưa có danh sách đầu mối khảo sát tại Sở/trường/UBND phường; khảo sát có thể "
        "lùi (xem PM-13).",
        "owner_text": "LD DVN, TVGS",
        "probability": 5,
        "status": "open",
        "title": "Dữ liệu CSVC/thiết bị ~1.670 trường sau sáp nhập (QĐ 5161/QĐ-UBND) không đồng nhất, "
        "thiếu, chậm cung cấp",
    },
    {
        "code": "PM-02",
        "due_date": None,
        "group_name": "Tiến độ",
        "impact": 5,
        "mitigation": "Theo dõi sát các mốc M1–M9 trên trang này; cảnh báo sớm khi đường tiến độ thực tế "
        "lệch kế hoạch. Liên hệ Crystal R02.",
        "note": "Đã xảy ra. Đến 15/10: mốc M1 (07/10) và M2 (13/10) chưa đạt; lập KH khảo sát chậm 11 "
        "ngày, khảo sát chậm 08 ngày, xác nhận yêu cầu chậm 06 ngày. Nhà thầu sẽ trình đề xuất "
        "điều chỉnh mốc khảo sát và biện pháp bù tiến độ (19–23/10). Xem PM-13.",
        "owner_text": "CĐT, LD DVN",
        "probability": 5,
        "status": "open",
        "title": "Tiến độ 120 ngày gấp, nhiều giai đoạn chồng lấn; vận hành thử chỉ 5 ngày (19–25/11) "
        "trước nghiệm thu",
    },
    {
        "code": "PM-03",
        "due_date": "2026-10-13",
        "group_name": "Phạm vi & Hợp đồng",
        "impact": 5,
        "mitigation": "Chốt bằng văn bản 13 nội dung Crystal kiến nghị, không trễ hơn mốc M2 "
        "(13/10/2026). Liên hệ Crystal R03.",
        "note": "Crystal nâng mức (R03, 08/10): phạm vi khảo sát chưa được CĐT xác nhận, ảnh hưởng "
        "phương thức triển khai và nghiệm thu; cần CĐT xác nhận bằng văn bản.",
        "owner_text": "CĐT, Crystal, LD DVN",
        "probability": 5,
        "status": "open",
        "title": "Phụ lục C tự mâu thuẫn (công nghệ backend, số trường, phạm vi dữ liệu, nền tảng lưu "
        "trữ, ứng dụng di động) trong hợp đồng trọn gói giá cố định",
    },
    {
        "code": "PM-04",
        "due_date": None,
        "group_name": "Pháp lý & Hồ sơ",
        "impact": 5,
        "mitigation": "Xác minh và xử lý ngay các sai sót hồ sơ có tính pháp lý.",
        "note": None,
        "owner_text": "CĐT, LD DVN",
        "probability": 5,
        "status": "open",
        "title": "Sai sót pháp lý hồ sơ dự thầu: ủy quyền ký bảo lãnh dự thầu ACB hết hiệu lực trước "
        "ngày ký; CCCD trùng giữa hai nhân sự chủ chốt LD DVN; MST/số E-TBMT sai",
    },
    {
        "code": "PM-05",
        "due_date": "2026-10-13",
        "group_name": "ATTT & Tuân thủ",
        "impact": 5,
        "mitigation": "Xác định sớm đơn vị lập và thời điểm thẩm định hồ sơ ATTT cấp độ 3 (trước M2). "
        "Liên hệ Crystal R05, R07.",
        "note": "Crystal xếp Rất cao (R05, 08/10): thiết kế ATTT, hạ tầng đang làm nhưng chưa có hồ sơ; "
        "theo dõi khi có hồ sơ thiết kế dự thảo.",
        "owner_text": "CĐT, LD DVN",
        "probability": 5,
        "status": "open",
        "title": "Hồ sơ ATTT cấp độ 3 và bảo vệ dữ liệu cá nhân chưa có mốc rõ ràng về đơn vị lập/thẩm "
        "định trước vận hành chính thức",
    },
    {
        "code": "PM-06",
        "due_date": None,
        "group_name": "Tổ chức & Nhân sự",
        "impact": 4,
        "mitigation": "Yêu cầu phân định trách nhiệm rõ tại các điểm giao diện. Liên hệ Crystal R06.",
        "note": "08/10: mô-đun mã định danh (VietFuture) không có trong báo cáo nhà thầu; CR cấu trúc mã "
        "định danh chờ nhà thầu lập (Crystal). 16/10: nhà thầu đã lập đề nghị thay đổi cấu trúc "
        "mã, trình CĐT 19–23/10 (xem PM-16).",
        "owner_text": "LD DVN, TVGS",
        "probability": 4,
        "status": "open",
        "title": "Phối hợp DTH (95%) – VietFuture (5%) tại các điểm giao diện tích hợp (mã định danh, "
        "API) dễ đùn đẩy trách nhiệm khi có lỗi",
    },
    {
        "code": "PM-07",
        "due_date": None,
        "group_name": "Hợp đồng",
        "impact": 4,
        "mitigation": "Theo dõi liên tục; chuẩn bị phương án gia hạn HĐ tư vấn nếu có dấu hiệu chậm; "
        "quyết định trước khi HĐ hết hạn. Liên hệ Crystal R12.",
        "note": None,
        "owner_text": "CĐT",
        "probability": 4,
        "status": "open",
        "title": "HĐ tư vấn giám sát & QLDA (150 ngày từ 24/8/2026) sát mốc hoàn thành gói triển khai "
        "(120 ngày từ 21/9/2026) — nguy cơ khoảng trống giám sát nếu trễ",
    },
    {
        "code": "PM-08",
        "due_date": "2026-10-31",
        "group_name": "Hành chính & Tài chính",
        "impact": 4,
        "mitigation": "Bổ sung hồ sơ nghiệm thu/thanh toán còn tồn trong tháng 10/2026.",
        "note": None,
        "owner_text": "CĐT",
        "probability": 4,
        "status": "open",
        "title": "Hồ sơ nghiệm thu/thanh toán các gói tư vấn trước (lập HSMT, thẩm định) còn thiếu hóa "
        "đơn, giấy đề nghị thanh toán, bản scan",
    },
    {
        "code": "PM-09",
        "due_date": None,
        "group_name": "Phụ thuộc bên ngoài",
        "impact": 3,
        "mitigation": "Xác định đầu mối và môi trường thử nghiệm. Liên hệ Crystal R10.",
        "note": None,
        "owner_text": "CĐT",
        "probability": 3,
        "status": "open",
        "title": "Liên thông CSDL ngành giáo dục và Cổng dữ liệu quốc gia phụ thuộc tiến độ/môi trường "
        "thử nghiệm của bên thứ ba, ngoài hợp đồng",
    },
    {
        "code": "PM-10",
        "due_date": None,
        "group_name": "Pháp lý",
        "impact": 3,
        "mitigation": "Chốt chế độ pháp lý áp dụng (kiến nghị #12 của Crystal).",
        "note": None,
        "owner_text": "CĐT",
        "probability": 3,
        "status": "open",
        "title": "Khung pháp lý chuyển tiếp chưa chốt (NĐ 45/2026 & TT 16/2024 hay NĐ 224/2026 & TT "
        "41/2026) ảnh hưởng biểu mẫu và tiêu chí nghiệm thu",
    },
    {
        "code": "PM-11",
        "due_date": None,
        "group_name": "Vận hành & Đào tạo",
        "impact": 3,
        "mitigation": "Lập kế hoạch đào tạo theo cụm, có phương án hỗ trợ trường vùng xa. Liên hệ "
        "Crystal R09.",
        "note": None,
        "owner_text": "LD DVN, CĐT",
        "probability": 3,
        "status": "open",
        "title": "Đào tạo diện rộng cho ~1.670 trường trong thời gian ngắn (5–18/11), độ phủ không đều, "
        "đặc biệt trường vùng xa",
    },
    {
        "code": "PM-12",
        "due_date": None,
        "group_name": "ATTT",
        "impact": 3,
        "mitigation": "Chốt số lần bắt buộc trong 120 ngày (Crystal đề xuất tối thiểu 1 lần trước nghiệm "
        "thu). Liên hệ Crystal R08.",
        "note": None,
        "owner_text": "CĐT, Crystal",
        "probability": 3,
        "status": "open",
        "title": "Tần suất kiểm thử xâm nhập/diễn tập khôi phục 'hằng quý' chưa khớp vòng đời 120 ngày",
    },
    {
        "code": "PM-13",
        "due_date": "2026-10-16",
        "group_name": "Tiến độ",
        "impact": 5,
        "mitigation": "QLDA đôn đốc CĐT cung cấp danh sách đầu mối và ban hành công văn phối hợp; DTH đề "
        "xuất trường đã có quan hệ sẵn (3 cấp học × 3 khu vực = 9 trường) và đầu mối UBND "
        "phường.",
        "note": "Đã xảy ra: M1/H2 07/10 không đạt. 14/10 nhà thầu gửi CĐT Kế hoạch khảo sát, danh sách "
        "đề xuất đơn vị, biểu mẫu; CĐT cử Mr. Khoa làm đầu mối chuyên môn. Chậm 11 ngày (lập KH "
        "khảo sát) và 08 ngày (khảo sát); CĐT còn phải thống nhất danh sách đơn vị và đầu mối. "
        "Nhà thầu lập hồ sơ đề xuất điều chỉnh mốc khảo sát và bù tiến độ, chờ trình (BC nhà "
        "thầu 16/10).",
        "owner_text": "CĐT, QLDA, LD DVN",
        "probability": 5,
        "status": "mitigating",
        "title": "Khảo sát hiện trạng có nguy cơ chậm do chưa có danh sách đầu mối phối hợp (Sở, trường, "
        "UBND xã/phường), ảnh hưởng mốc M1 07/10",
    },
    {
        "code": "PM-14",
        "due_date": None,
        "group_name": "Tiến độ",
        "impact": 3,
        "mitigation": "Nhà thầu điều chỉnh theo kết quả khảo sát; Crystal chỉ ghi nhận khối lượng sau "
        "khi H2, H3 được chấp thuận. Liên hệ Crystal R13.",
        "note": "Tiếp diễn: nhà thầu đã hoàn thành các mô-đun danh mục, điểm trường, hồ sơ công "
        "trình/khối nhà/phòng trước khi yêu cầu được xác nhận; phải điều chỉnh theo kết quả khảo "
        "sát (BC nhà thầu 16/10).",
        "owner_text": "LD DVN, TVGS",
        "probability": 3,
        "status": "open",
        "title": "Xây dựng hệ thống trước khi yêu cầu được xác nhận (khảo sát chưa xong), có thể phải "
        "làm lại; khối lượng chỉ ghi nhận sau khi H2, H3 được chấp thuận",
    },
    {
        "code": "PM-15",
        "due_date": None,
        "group_name": "Hồ sơ & Nghiệm thu",
        "impact": 3,
        "mitigation": "Biểu mẫu khảo sát có chữ ký đơn vị, scan lưu hồ sơ; Crystal chỉ ký nghiệm thu khi "
        "số biểu mẫu khớp danh sách trường. Liên hệ Crystal R14.",
        "note": "Mới trong CRY-SGD-WR-02 (08/10).",
        "owner_text": "LD DVN, TVGS",
        "probability": 3,
        "status": "open",
        "title": "Kết quả khảo sát thiếu xác nhận của đơn vị được khảo sát, không đủ căn cứ nghiệm thu",
    },
    {
        "code": "PM-16",
        "due_date": "2026-10-23",
        "group_name": "Phạm vi & Hợp đồng",
        "impact": 3,
        "mitigation": "Nhà thầu đề xuất tăng số thứ tự lên 04 ký tự; đã lập đề nghị thay đổi, trình CĐT "
        "19–23/10. CĐT xem xét (xem K18).",
        "note": "Nêu tại BC nhà thầu 09/10–15/10 (16/10). Liên quan PM-06.",
        "owner_text": "LD DVN, CĐT",
        "probability": 3,
        "status": "mitigating",
        "title": "Quy tắc mã định danh thiết bị trong Báo cáo KT-KT chỉ dành 02 ký tự cho số thứ tự, "
        "không đủ khi hơn 99 thiết bị; ảnh hưởng chức năng sinh mã định danh",
    },
]

# (no, title, reason, due date)
DECISIONS: list[tuple[int, str, str | None, str | None]] = [
    (
        1,
        "Chốt danh mục hồ sơ đường cơ sở: E-HSDT được chấp thuận, kế hoạch triển khai, tiến độ chi tiết, "
        "danh sách đơn vị triển khai",
        "Kiến nghị của Crystal, Đề cương giám sát mục XVI (28/8/2026)",
        "2026-10-13",
    ),
    (
        2,
        "Phạm vi dữ liệu chưa nhất quán: mục 1.1.8 Phụ lục C giới hạn dữ liệu CSVC/thiết bị, nhưng mục "
        "1.1.2, 2.2 lại đề cập dữ liệu học sinh, giáo viên (CCCD), lịch học, điểm số",
        "Kiến nghị của Crystal, Đề cương giám sát mục XVI (28/8/2026)",
        "2026-10-13",
    ),
    (
        3,
        "Nền tảng lưu trữ/hạ tầng chưa nhất quán: Drive API, AWS EC2/ELB/CloudWatch vs yêu cầu dữ liệu "
        "lưu tại Việt Nam",
        "Kiến nghị của Crystal, Đề cương giám sát mục XVI (28/8/2026)",
        "2026-10-13",
    ),
    (
        4,
        "Ứng dụng di động: mục 1 yêu cầu PWA/QR kiểm kê nhưng mục 1.1.8 ghi 'không bao gồm ứng dụng di "
        "động' — xác định PWA có thuộc phạm vi nghiệm thu không",
        "Kiến nghị của Crystal, Đề cương giám sát mục XVI (28/8/2026)",
        "2026-10-13",
    ),
    (
        5,
        "Công nghệ backend chưa thống nhất: Node.js/Express (mục 3.1.3) vs .NET Core kết hợp Node.js",
        "Kiến nghị của Crystal, Đề cương giám sát mục XVI (28/8/2026)",
        "2026-10-13",
    ),
    (
        6,
        "Số lượng đơn vị trường chưa khớp: 1.670 trường vs 'từ 2.341 lên hơn 3.500 trường' (mục 5.1.1)",
        "Kiến nghị của Crystal, Đề cương giám sát mục XVI (28/8/2026)",
        "2026-10-13",
    ),
    (
        7,
        "Chốt ma trận vai trò người dùng (Sở, UBND xã/phường, Hiệu trưởng, cán bộ thiết bị, giáo viên, "
        "kế toán, quản trị viên) làm căn cứ kiểm thử phân quyền",
        "Kiến nghị của Crystal, Đề cương giám sát mục XVI (28/8/2026)",
        "2026-10-13",
    ),
    (
        8,
        "Xác định đơn vị lập và thời điểm thẩm định hồ sơ đề xuất cấp độ ATTT cấp độ 3 (điều kiện bắt "
        "buộc trước vận hành chính thức)",
        "Kiến nghị của Crystal, Đề cương giám sát mục XVI (28/8/2026)",
        "2026-10-13",
    ),
    (
        9,
        "Kiểm thử xâm nhập và diễn tập khôi phục ghi 'hằng quý' — xác định số lần bắt buộc trong 120 "
        "ngày (Crystal đề xuất tối thiểu 1 lần trước nghiệm thu)",
        "Kiến nghị của Crystal, Đề cương giám sát mục XVI (28/8/2026)",
        "2026-10-13",
    ),
    (
        10,
        "Xác định đầu mối và môi trường thử nghiệm liên thông CSDL ngành giáo dục / Cổng dữ liệu quốc "
        "gia (phụ thuộc bên thứ ba)",
        "Kiến nghị của Crystal, Đề cương giám sát mục XVI (28/8/2026)",
        "2026-10-13",
    ),
    (
        11,
        "Thống nhất cơ chế quản lý hồ sơ điện tử, quyền truy cập môi trường cho TVGS, nơi lưu trữ bằng "
        "chứng chứa dữ liệu nhạy cảm",
        "Kiến nghị của Crystal, Đề cương giám sát mục XVI (28/8/2026)",
        "2026-10-13",
    ),
    (
        12,
        "Chế độ pháp lý chuyển tiếp: tiếp tục NĐ 45/2026/NĐ-CP & TT 16/2024/TT-BTTTT hay chuyển sang NĐ "
        "224/2026/NĐ-CP & TT 41/2026/TT-BKHCN",
        "Kiến nghị của Crystal, Đề cương giám sát mục XVI (28/8/2026)",
        "2026-10-13",
    ),
    (
        13,
        "Phương án điều chỉnh thời gian HĐ tư vấn giám sát (150 ngày từ 24/8/2026) nếu gói triển khai "
        "được gia hạn",
        "Kiến nghị của Crystal, Đề cương giám sát mục XVI (28/8/2026)",
        "2026-10-13",
    ),
    (
        14,
        "Cung cấp danh sách đầu mối khảo sát (trường, phòng/bộ phận, UBND xã/phường) và ban hành công "
        "văn/Kế hoạch phối hợp khảo sát",
        "Nhà thầu kiến nghị tại BC tuần; Crystal đề nghị QLDA đôn đốc CĐT. 14/10: nhà thầu đã gửi Kế "
        "hoạch khảo sát, danh sách đề xuất đơn vị khảo sát, biểu mẫu; CĐT đã cử Mr. Khoa là đầu mối hỗ "
        "trợ kỹ thuật, chuyên môn phần mềm. Còn lại: CĐT thống nhất danh sách đơn vị và đầu mối phối "
        "hợp, ban hành Kế hoạch phối hợp khảo sát, đề nghị UBND xã/phường cử cán bộ (BC nhà thầu 16/10).",
        "2026-10-16",
    ),
    (
        15,
        "Xác nhận bằng văn bản danh sách trường khảo sát theo cấp học và tính đại diện cho hơn 2.000 "
        "trường; ban hành biểu mẫu khảo sát kèm công văn gửi trường",
        "Kiến nghị 1 của Crystal (CRY-SGD-WR-02, 08/10), hạn đề nghị 16/10. 14/10 nhà thầu đã gửi danh "
        "sách đề xuất đơn vị khảo sát và biểu mẫu; chờ CĐT xác nhận danh sách (BC nhà thầu 16/10).",
        "2026-10-16",
    ),
    (
        16,
        "Ký biên bản họp khởi động và văn bản thông qua Kế hoạch tiến độ triển khai để khóa đường cơ sở "
        "(H0)",
        "Kiến nghị 3 của Crystal (08/10). Đến BC 16/10: biên bản họp khởi động, văn bản thông qua kế "
        "hoạch tiến độ và sơ đồ tổ chức nhân sự vẫn là dự thảo chờ ký; nhà thầu đề nghị ký một lần khi "
        "đủ đầu mối.",
        "2026-10-16",
    ),
    (
        17,
        "Cung cấp Quyết định phê duyệt kết quả lựa chọn nhà thầu (PL-02) để hoàn thiện căn cứ các biên "
        "bản",
        "Kiến nghị 4 của Crystal (08/10), chuyển tiếp từ tuần 01.",
        None,
    ),
    (
        18,
        "Xem xét đề nghị thay đổi cấu trúc mã định danh thiết bị (tăng số thứ tự từ 02 lên 04 ký tự)",
        "Nhà thầu lập đề nghị, trình CĐT 19–23/10 (BC nhà thầu 09/10–15/10). Liên quan PM-16.",
        "2026-10-23",
    ),
    (
        19,
        "Xem xét hồ sơ đề xuất điều chỉnh mốc hoàn thành khảo sát và biện pháp bù tiến độ",
        "Nhà thầu đã lập hồ sơ, chờ trình CĐT (19–23/10, theo lịch họp thống nhất) do khảo sát chậm 08 "
        "ngày (BC nhà thầu 09/10–15/10). Liên quan PM-02, PM-13.",
        "2026-10-23",
    ),
]
