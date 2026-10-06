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
