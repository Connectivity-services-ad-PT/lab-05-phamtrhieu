# RUN_COMPOSE.md – Hướng dẫn chạy Lab 05 (Notification Service)

Tài liệu này hướng dẫn cách chạy và kiểm thử stack Docker Compose của dịch vụ **Notification Service** (`team-notify`).

---

## 1. Clone repo và chuẩn bị

```bash
git clone <repo-url>
cd lab-5-ngocviphacker
```

Cài đặt các dependencies cần thiết cho Postman/Newman cục bộ (tuỳ chọn):

```bash
npm install
```

---

## 2. Thiết lập môi trường

Sao chép tệp cấu hình môi trường mẫu:

```bash
cp .env.example .env
```

Nếu muốn chạy database với thông tin khác, bạn có thể chỉnh sửa các giá trị `POSTGRES_USER`, `POSTGRES_PASSWORD`, và `POSTGRES_DB` trong `.env`.

---

## 3. Khởi động Stack Docker Compose

Khởi động các dịch vụ trong nền:

```bash
docker compose up -d --build
```

Lệnh này sẽ khởi chạy 3 container:
1. `fit4110-db-lab05` (PostgreSQL - lưu lịch sử log gửi notification).
2. `fit4110-ai-lab05` (AI Service mock cung cấp endpoint phân tích `/predict` trên port `9000`).
3. `fit4110-api-lab05` (Notification Service API trên port `8000`).

Theo dõi log của các container đang hoạt động:

```bash
docker compose logs -f
```

---

## 4. Kiểm tra trạng thái sẵn sàng (Readiness Check)

Kiểm tra trạng thái hoạt động của từng service:

```bash
# 1. API Health (Kiểm tra kết nối DB và AI Service)
curl http://localhost:8000/health

# 2. AI Service Health
curl http://localhost:9000/health

# 3. Database Readiness
docker exec -it fit4110-db-lab05 pg_isready -U lab05
```

---

## 5. Thử nghiệm gửi Event qua cURL

Gửi thử một event alert để Notification Service tiếp nhận, log vào DB và gọi AI Service kiểm tra:

```bash
curl -X POST http://localhost:8000/events/alert.created \
  -H "Authorization: Bearer local-dev-token" \
  -H "Content-Type: application/json" \
  -d '{
    "eventId": "550e8400-e29b-41d4-a716-446655440000",
    "eventType": "alert.created",
    "alertId": "ALT-2026-05-19-001",
    "correlationId": "COR-2026-05-19-001",
    "source": "core-business-service",
    "severity": "HIGH",
    "alertVersion": 1,
    "occurredAt": "2026-05-19T10:30:00Z",
    "payload": {
      "title": "Truy cập trái phép",
      "message": "Phát hiện chuyển động lạ tại cổng chính",
      "source": "sensor-gate-01"
    },
    "channels": ["telegram", "email", "app"]
  }'
```

---

## 6. Chạy Newman test

Kiểm thử tự động toàn bộ API flow trên Compose:

```bash
npm run test:compose
```

Báo cáo chi tiết sẽ được xuất ra tại thư mục `reports/`.

---

## 7. Dừng hệ thống

Dừng toàn bộ stack và dọn dẹp các container:

```bash
docker compose down
```

Nếu muốn xóa toàn bộ database data volume (cho lần chạy sạch tiếp theo):

```bash
docker compose down -v
```