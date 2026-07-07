# KỊCH BẢN TRÌNH BÀY DEMO BUỔI 6
## Nhóm A7: Notification Service (Product A)

Dưới đây là kịch bản trình bày chi tiết bám sát **6 bước** và **tiêu chí chấm điểm** của giảng viên. Bạn có thể mở file này để đọc trực tiếp khi thuyết trình.

---

### 1. VAI TRÒ CỦA NHÓM (1.0 điểm)
* **Tên Dịch Vụ:** Notification Service (Dịch vụ gửi cảnh báo).
* **Vai trò trong hệ thống Smart Campus:** 
  * Tiếp nhận các sự kiện cảnh báo từ hệ thống và gửi thông báo đa kênh đến người dùng cuối.
  * Là **Provider** (Bên cung cấp dịch vụ) đối với dịch vụ **Core Business (nhóm A6)**. Nhóm A6 đóng vai trò là Consumer sẽ chủ động gọi API sang nhóm em.
  * Đồng thời, nhóm em hỗ trợ tích hợp trực tiếp với **AI Vision Service (team-vision)** để nhận trực tiếp các cảnh báo lỗi camera/sự cố an ninh từ ảnh giám sát.

---

### 2. INPUT (DỮ LIỆU ĐẦU VÀO)
* **Dữ liệu nhận vào:** Sự kiện cảnh báo dạng JSON Payload qua giao thức **REST API** (HTTP POST).
* **Các nguồn kết nối:**
  1. **Nguồn chính (Chuẩn luồng):** Nhận từ dịch vụ **Core Business (A6)** qua endpoint `POST /events/alert.created`.
  2. **Nguồn liên kết trực tiếp:** Nhận từ dịch vụ **AI Vision Service (team-vision)** qua endpoint `POST /api/v1/alerts`.
* **Cấu trúc JSON Input mẫu (từ Core A6):**
  ```json
  {
    "eventId": "550e8400-e29b-41d4-a716-446655440000",
    "eventType": "alert.created",
    "alertId": "ALT-2026-05-19-001",
    "correlationId": "COR-2026-05-19-001",
    "source": "core-business-service",
    "severity": "HIGH",
    "alertVersion": 1,
    "payload": {
      "title": "Truy cập trái phép",
      "message": "Phát hiện chuyển động lạ tại cổng chính"
    },
    "channels": ["telegram", "email", "app"]
  }
  ```
* **Cấu trúc JSON Input mẫu (từ AI Vision):**
  ```json
  {
    "source": "ai-vision-service",
    "title": "Cảnh báo ảnh mờ",
    "message": "Phát hiện chất lượng ảnh thấp (mờ/nhiễu) tại camera Gate A",
    "severity": "HIGH",
    "data": {
      "camera_id": "cam-01",
      "location": "Gate A"
    }
  }
  ```

---

### 3. XỬ LÝ NGHIỆP VỤ (1.0 điểm & Xử lý lỗi 1.0 điểm)
Khi nhận được request từ các nhóm đối tác, dịch vụ tiến hành xử lý qua các bước:
1. **Xác thực (chỉ áp dụng luồng chính từ Core):** Kiểm tra mã bảo mật ở Header `Authorization: Bearer local-dev-token`. Luồng đi trực tiếp từ AI Vision được mở public để hai nhóm test nhanh qua VPN.
2. **Validate Schema:** Kiểm tra cấu trúc JSON đầu vào. Đối với luồng Core, bắt buộc `eventId` phải đúng định dạng **UUID**. Nếu sai sẽ trả về lỗi `422 Unprocessable Entity` (chuẩn RFC 7807).
3. **Phân tích thông minh (AI Integration):** Gọi API sang dịch vụ **AI Service** (`/predict` trên port 9000) để phân tích mức độ cảnh báo (YOLO model).
4. **Phân phối đa kênh:** Duyệt qua mảng `channels` yêu cầu (hoặc tự động dịch theo mức độ nghiêm trọng `severity` đối với cảnh báo từ AI Vision). Với mỗi kênh, hệ thống ghi nhận lịch sử gửi vào cơ sở dữ liệu **PostgreSQL**.
5. **Xử lý lỗi / Timeout:**
   * Các cuộc gọi sang AI Service hoặc kết nối Database được cấu hình **Timeout tối đa 2.0 giây** để tránh treo request vô hạn.
   * Nếu Database PostgreSQL gặp sự cố, hệ thống có cơ chế **Fallback tự động lưu vào bộ nhớ tạm (In-memory dict)**, đảm bảo API vẫn phản hồi thành công cho nhóm đối tác mà không bị crash.

---

### 4. OUTPUT (DỮ LIỆU ĐẦU RA)
* **Kết quả trả về:** Dịch vụ phản hồi mã trạng thái HTTP **`202 Accepted`** (xác nhận đã tiếp nhận và xếp hàng gửi).
* **JSON Output mẫu:**
  ```json
  {
    "eventId": "550e8400-e29b-41d4-a716-446655440000",
    "status": "queued",
    "processedAt": "2026-06-17T17:23:39.220091+00:00"
  }
  ```

---

### 5. OUTPUT GỬI CHO AI?
* Dịch vụ Notification là **điểm cuối của luồng tích hợp** (chịu trách nhiệm trực tiếp đẩy thông báo đến các ứng dụng Telegram, Email, App của người dùng cuối), nên nhóm em **không gửi tiếp output sang dịch vụ nào khác** trong hệ thống Smart Campus.

---

### 6. MINH CHỨNG DEMO (1.5 điểm)
*(Show trực tiếp cho thầy xem)*

1. **Giao diện Web Dashboard:** Mở trình duyệt vào **`http://localhost:8000/`**.
   * Show trạng thái của **Notification API, PostgreSQL Database, AI Service** đều báo màu xanh lá cây (`HOẠT ĐỘNG`).
   * Show bảng lịch sử thông báo lấy real-time từ Database.
2. **Kiểm thử tích hợp chéo (Bắt tay thật):**
   * **Test với nhóm A6 (Core Business):** Nhờ nhóm A6 bắn thử sự kiện qua Radmin IP của bạn (`26.95.36.20:8000/events/alert.created`). Dòng thông báo mới sẽ lập tức xuất hiện trên Dashboard mà không cần reload trang.
   * **Test với nhóm AI Vision (team-vision):** Nhờ nhóm AI Vision bắn thử cảnh báo qua Radmin IP của bạn (`26.95.36.20:8000/api/v1/alerts`). Xác minh bảng thông báo hiển thị đúng nội dung cảnh báo từ camera của họ gửi sang.
3. **Container Status:** Mở Terminal chạy `docker compose ps` để show toàn bộ container đang chạy bình thường.

