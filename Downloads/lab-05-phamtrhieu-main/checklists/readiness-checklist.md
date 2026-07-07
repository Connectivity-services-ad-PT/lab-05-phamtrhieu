# Readiness Checklist – Lab 05

Đây là danh sách kiểm tra (checklist) để đảm bảo stack Docker Compose của bạn đã sẵn sàng trước khi gửi bài. Hãy tick vào mỗi mục sau khi hoàn thành.

- [x] **Database ready:** container DB đã chạy và phản hồi `pg_isready`. Kiểm tra bằng `docker exec -it fit4110-db-lab05 pg_isready -U $POSTGRES_USER`.
- [x] **AI service ready:** container AI service trả về `200` cho endpoint `/health` và `/predict` hoạt động.
- [x] **API ready:** container API trả `200` cho `/health` và có thể tạo/lấy readings khi token hợp lệ.
- [x] **Environment variables:** `.env` đã được thiết lập đúng (APP_PORT, POSTGRES_USER, AUTH_TOKEN,…). Không sử dụng secret thật; lưu secret vào `.env` cục bộ, commit `.env.example`.
- [x] **Network & Ports:** mạng `team-internal` hoạt động; API gọi được AI bằng hostname `ai-service`; ports 8000 (API), 9000 (AI) và 5432 (DB) được map đúng.
- [x] **Image tags:** bạn đã build image với tag `v0.1.0-team-notify` và push lên registry.

Ghi chú thêm những vấn đề gặp phải hoặc điều chỉnh tại đây:

```
- Đã cấu hình và đổi tên service API mặc định sang Notification Service để phù hợp với định hướng nhóm.
- Đã liên kết API với database PostgreSQL thực sự thông qua driver psycopg2 để ghi nhận lịch sử gửi thông báo.
- Đã tích hợp API gọi sang AI service thông qua mạng cầu nối Compose.
```