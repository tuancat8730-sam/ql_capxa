# Câu hỏi mở

Ghi theo SPEC mục 0.3: chỗ mơ hồ → chọn phương án mặc định, ghi lại ở đây, báo cuối milestone.

## Từ phụ lục SPEC
1. Hợp đồng và giá trúng Gói 03; giá trị HĐ 73, 74 (Gói 07, 08). → Để `NULL`, UI hiện "Chưa có dữ liệu".
2. Bản gốc bảo lãnh Gói 05 để xác nhận ngày hết hạn (đang là [OCR]). → M3.
3. Gói 04 bảo lãnh tạm ứng và Gói 05 bảo đảm thực hiện đã phát hành chưa. → M3 tạo bản ghi `missing`.
4. Gói 02: hợp đồng sửa lại điều khoản nào.
5. Danh sách ngày lễ áp dụng cho SLA. → M6.
6. Tên miền, tài khoản AWS và môi trường triển khai thực tế. → M8.

## Phát sinh ở M2 (seed)
7. **Tên và phạm vi từng gói thầu** chưa có trong SPEC. Mặc định `name = "Gói thầu số 0N"`, `scope_summary = NULL`.
8. **Loại gói (`package_type`)**: SPEC chỉ nêu Gói 06 là tư vấn. Mặc định: Gói 01–05 = `goods`, Gói 06–08 = `consulting` (Gói 07/08 là suy đoán, vì có HĐ TVGS ở một trong hai gói).
9. **Loại hợp đồng, hình thức/phương thức lựa chọn nhà thầu** chưa nêu (trừ Gói 02 = trọn gói). Để `NULL`.
10. **Gói 06, ngày hiệu lực**: văn bản ghi kết thúc 22/01/2027, trong khi 24/9/2026 + 120 ngày − 1 = 21/01/2027. Nếu hiệu lực là 25/9 thì khớp. Mặc định: giữ 22/01/2027 và bật `end_date_override` (cờ mức `info`).
11. **Gói 02**: chưa rõ ngày ký và giá trị HĐ 54; chỉ nạp các điểm sai khác đã nêu (90 so với 60 ngày, tài khoản 8171939, trọn gói có điều chỉnh giá, phạt 10%/tuần tối đa 20%). Quy tắc ngày kết thúc bỏ qua vì thiếu ngày bắt đầu.
12. **Gói 01** cũng hiện cờ `END_DATE_MISMATCH` (văn bản ghi 18/9, tính ra 17/9) vì SPEC 14.3 nêu rõ sai khác này; AC của M2 chỉ yêu cầu Gói 02 và Gói 04 phải có cờ.
13. **Gói 05, liên danh**: chưa rõ bên nào đứng đầu. Mặc định P&N = `lead` (nêu trước). Tạm ứng theo thành viên chưa nạp (không biết bảo lãnh TPBank/BIDV của bên nào).
14. **Gói 05, tạm ứng 30%** là suy ra từ tổng hai bảo lãnh tạm ứng (4.079.992.500 = 30% × 13.599.975.000), ghi chú trong `data_quality_note`.
15. **Trạng thái và giai đoạn hiện tại** mặc định `contract_signed` / `S3_EXECUTION` cho gói đã có hợp đồng; Gói 03 `bidding` / `S2_SELECTION`. Sức khỏe gói (M7) chưa tính: `grey`.

## Phát sinh ở M4 (tài liệu)
16. **Loại tài liệu cho một số hạng mục checklist** không có mã chuẩn trong SPEC 4.6 (Mẫu 02.a, chứng nhận bảo hành, biên bản vận hành thử, sản phẩm bàn giao của gói tư vấn): dùng `other` kèm tiêu đề hạng mục.
17. **Hạng mục "không bắt buộc"**: SPEC ghi "(nếu có)" sau kiểm định/hiệu chuẩn. Áp dụng cho cả chứng nhận bảo hành; CO, CQ để bắt buộc. Cần xác nhận.
18. **Hạn của hạng mục checklist** (`due_offset_days`) tính từ ngày hiệu lực hợp đồng (hoặc ngày ký): bảo lãnh thực hiện +7 ngày, bảo lãnh tạm ứng +0. Các hạng mục khác chưa có hạn.
19. **Chặn trùng tệp**: SPEC 4.6 nói "chặn", mục 9 nói "cảnh báo". Chọn chặn (409) trong cùng gói; tài liệu cấp dự án không bị chặn.
20. **Giám đốc (director) quản lý quyền xem tài liệu nhạy cảm** qua API, nhưng giao diện chỉ làm cho admin vì danh sách người dùng chỉ admin được gọi.

## Phát sinh ở M5 (tiến độ)
21. **Dữ liệu giai đoạn ban đầu**: SPEC không nêu ngày kế hoạch của từng giai đoạn. Chỉ nạp những gì suy ra được: gói đã ký hợp đồng thì S2 (lựa chọn nhà thầu) hoàn thành; S3 lấy ngày bắt đầu và kết thúc của hợp đồng. Gói 03 đang `bidding` thì S2 đang thực hiện. S1, S4, S5 để trống. Hệ quả: tiến độ các gói đã ký hiện 20% (S2 × trọng số 20).
22. **QL-06**: các cột ngày lấy từ ngày văn bản của tài liệu theo loại (QĐ phê duyệt E-HSMT, E-TBMT, biên bản mở thầu, báo cáo đánh giá, QĐ phê duyệt KQLCNT) và ngày ký hợp đồng. Ô "trễ" so với ngày kết thúc kế hoạch của giai đoạn S2. "Số nhà thầu" chưa có nguồn dữ liệu.
23. **Nhật ký hằng ngày**: thêm hai trường theo mục 15.5d (nhân lực, thời tiết) và `client_id` cho Idempotency-Key; không có trong mục 3.15.

## Phát sinh ở M6 (rủi ro, vướng mắc)
24. **Điểm của 10 rủi ro seed** (xác suất × tác động) không có trong SPEC 14.6 — đã gán đánh giá ban đầu (cao nhất: Gói 03 chậm hợp đồng 4×5 và bảo lãnh tạm ứng Gói 05 5×4). Chủ trì, hạn, biện pháp chi tiết để trống hoặc ghi ngắn; cần Giám đốc QLDA rà soát.
25. **Ngày lễ cho SLA cấp 2** chưa có (câu hỏi mở 5): bảng `holidays` để trống, admin nhập qua `/admin/holidays`. Đến khi nhập, cấp 2 chỉ bỏ qua thứ Bảy, Chủ nhật.
26. **Đóng vướng mắc**: SPEC chỉ nêu Giám đốc đóng cấp 3. Áp dụng: cấp 1–2 người có quyền ghi đóng được, cấp 3 chỉ Giám đốc.

27. **`CROSS_PKG_DEPENDENCY` khi gói cung cấp chưa có hợp đồng.** SPEC 14.7 muốn cảnh báo này ngay sau seed, nhưng HĐ Gói 04 và 05 kết thúc 12–13/11/2026, trước ngày TVGS (~13/12/2026). Gói 03 chưa ký nên chưa có ngày kết thúc. Quy tắc đang coi gói cung cấp còn mở mà chưa có hợp đồng là "chưa xác nhận được TVGS bao phủ" và báo nếu hợp đồng TVGS kết thúc trong 90 ngày tới (`UNSIGNED_SUPPLY_HORIZON_DAYS`). Ngày 13/12/2026 của HĐ 73 là ước tính từ SPEC 14.6, cần xác nhận; 90 ngày là giả định cần Giám đốc QLDA duyệt.
28. **Vai trò hợp đồng tư vấn** (`consulting_role`): Gói 06 = TVQLDA, Gói 07 = TVGS, Gói 08 = khác. Gói 08 là gì (kiểm toán?) SPEC chưa nói.
