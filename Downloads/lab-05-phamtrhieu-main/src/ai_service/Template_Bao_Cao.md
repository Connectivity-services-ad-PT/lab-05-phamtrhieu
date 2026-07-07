

TRƯỜNG ĐẠI HỌC ĐẠI NAM

KHOA CÔNG NGHỆ THÔNG TIN

BÁO CÁO BÀI TẬP LỚN

Học phần: Dịch vụ kết nối và Công nghệ nền tảng (FIT4110)

Đề tài: Xây dựng service [TÊN SERVICE] trong Smart Campus Operations Platform

Mã nhóm: ____________ Lớp:

Sản phẩm (Product): ____________________________

Service phụ trách: ____________________________

Giảng viên hướng dẫn: ____________________________

Năm học: ____________________________



Danh sách thành viên:




 | 



STT | 



Họ và tên | 



Mã sinh viên | 



Vai trò


 | 



1 | 



 | 



 | 






 | 



2 | 



 | 



 | 






 | 



3 | 



 | 



 | 






 | 



4 | 



 | 



 | 







I. Giới thiệu

1.1. Bối cảnh

[ Hướng dẫn: Giới thiệu ngắn gọn hệ thống Smart Campus Operations Platform và vị trí service của nhóm trong đó. 3-5 câu. ]

............................................................................................................

1.2. Mục tiêu của service

[ Hướng dẫn: Service của nhóm sinh ra để giải quyết vấn đề gì? Phát biểu bằng 1-2 câu nghiệp vụ, không phải mô tả kỹ thuật. ]

............................................................................................................

1.3. Phạm vi

[ Hướng dẫn: Liệt kê service LÀM gì và KHÔNG làm gì, để xác định ranh giới trách nhiệm. ]

Service có làm:

....................................................................

....................................................................

Service không làm:

....................................................................



II. Phân tích nghiệp vụ (phần trọng tâm)

Lưu ý: Đây là phần phân biệt nhóm hiểu việc mình làm với nhóm chỉ trung chuyển dữ liệu. Phải trình bày rõ: service nhận gì, biến đổi như thế nào, ra quyết định gì, gửi đi đâu.

2.1. Vai trò nghiệp vụ

[ Hướng dẫn: Mô tả service đóng vai gì trong hệ thống bằng ngôn ngữ nghiệp vụ. Ví dụ: 'làm sạch và phân loại dữ liệu cảm biến', 'quyết định cho phép ra/vào'. ]

............................................................................................................

2.2. Vị trí trong kiến trúc

[ Hướng dẫn: Điền bảng phụ thuộc: service nhận dữ liệu từ ai, gửi cho ai, bằng cơ chế REST sync hay MQTT async. Bám theo Dependency Map của lớp. ]




 | 



Quan hệ | 



Nhóm đối tác | 



Mục đích | 



Cơ chế (REST/MQTT)


 | 



Nhận từ  | 



 | 



 | 






 | 



Nhận từ  | 



 | 



 | 






 | 



Gửi tới  | 



 | 



 | 






 | 



Gửi tới  | 



 | 



 | 





2.3. Đặc tả dữ liệu đầu vào

[ Hướng dẫn: Nguồn vào (topic MQTT hoặc REST endpoint) và schema payload nhận được. Dán schema JSON thật. ]

Nguồn vào (topic/endpoint): ____________________________

Schema đầu vào:

{  "...": "...",  "...": "..."}

2.4. Logic xử lý nghiệp vụ

[ Hướng dẫn: Đây là phần cốt lõi. Mô tả TỪNG BƯỚC service xử lý dữ liệu. Tối thiểu phải thể hiện được: kiểm tra hợp lệ, chuẩn hóa, làm giàu, phân loại/quyết định, tạo đầu ra. ]




 | 



Bước | 



Service làm gì ở bước này


 | 



1. VALIDATE | 






 | 



2. NORMALIZE | 






 | 



3. ENRICH | 






 | 



4. CLASSIFY / DECIDE | 






 | 



5. PRODUCE | 





2.5. Quy tắc nghiệp vụ

[ Hướng dẫn: Liệt kê các quy tắc cụ thể service áp dụng, kèm ngưỡng/điều kiện rõ ràng. Ví dụ: nhiệt độ >= 40 thì status = danger. ]




 | 



Điều kiện | 



Kết quả / hành động


 | 



 | 






 | 



 | 






 | 



 | 






 | 



 | 





2.6. Đặc tả dữ liệu đầu ra

[ Hướng dẫn: Đích gửi (topic/endpoint) và schema event đầu ra. Dán schema JSON thật. ]

Đích gửi (topic/endpoint): ____________________________

Schema đầu ra:

{  "...": "...",  "...": "..."}

2.7. Quyết định thiết kế

[ Hướng dẫn: Những lựa chọn nhóm tự đưa ra và lý do. Ví dụ: chọn ngưỡng confidence 0.5, chọn cooldown 5 giây, chọn gửi snapshot_url thay vì base64. ]




 | 



Quyết định | 



Lý do


 | 



 | 






 | 



 | 






 | 



 | 







III. Thiết kế API / hợp đồng dịch vụ

3.1. Danh sách endpoint / topic

[ Hướng dẫn: Liệt kê các endpoint REST hoặc topic MQTT service cung cấp/sử dụng. ]




 | 



Endpoint / Topic | 



Phương thức / Vai trò | 



Mô tả


 | 



 | 



 | 






 | 



 | 



 | 






 | 



 | 



 | 





3.2. Hợp đồng OpenAPI

[ Hướng dẫn: Tóm tắt openapi.yaml của service (nếu là service REST). Dán link file trong repo. Nêu service dùng versioning, security scheme gì. ]

Đường dẫn openapi.yaml trong repo: ............................................................................................................

3.3. Mã lỗi và xử lý lỗi

[ Hướng dẫn: Liệt kê các mã lỗi service trả về và ý nghĩa. Nếu dùng REST, theo chuẩn RFC 7807. ]




 | 



Mã lỗi | 



Khi nào | 



Nội dung trả về


 | 



400 | 



 | 






 | 



401 | 



 | 






 | 



503 | 



 | 







IV. Triển khai kỹ thuật

4.1. Kiến trúc service

[ Hướng dẫn: Liệt kê các container trong stack của nhóm (ví dụ api, db, worker). Vẽ sơ đồ nếu có. ]

............................................................................................................

4.2. Dockerfile và Docker Compose

[ Hướng dẫn: Mô tả ngắn cách đóng gói: base image, các service trong compose, network, volume. Dán đoạn compose chính. ]

# trích docker-compose.ymlservices:  api:    ...

4.3. Biến môi trường

[ Hướng dẫn: Liệt kê các biến trong .env.example và ý nghĩa. KHÔNG dán mật khẩu thật vào báo cáo. ]




 | 



Biến | 



Ý nghĩa


 | 



 | 






 | 



 | 






 | 



 | 





4.4. Healthcheck và readiness

[ Hướng dẫn: Mô tả cách service báo healthy/ready: endpoint /health trả gì, healthcheck trong compose, điều kiện readiness. ]

............................................................................................................



V. Tích hợp liên nhóm

5.1. Sơ đồ tích hợp

[ Hướng dẫn: Service của nhóm tích hợp với những nhóm nào. Vẽ hoặc mô tả luồng. ]

............................................................................................................

5.2. Cấu hình mạng (Radmin VPN)

[ Hướng dẫn: Nêu máy demo của nhóm, Radmin IP, network đã join. Cách cấu hình .env dùng Radmin IP của nhóm đối tác. ]

Máy demo: ____________   Radmin IP của nhóm: ____________   Network: ____________




 | 



Nhóm đối tác | 



Radmin IP : Port | 



Dùng để làm gì


 | 



 | 



 | 






 | 



 | 



 | 





5.3. Hợp đồng với nhóm đối tác

[ Hướng dẫn: Dẫn chiếu biên bản chốt hợp đồng API đã ký ở Buổi 2. Nêu endpoint/topic, schema đã thống nhất. ]

............................................................................................................

5.4. Kết quả test tích hợp

[ Hướng dẫn: Trình bày kết quả gọi chéo /health qua Radmin IP và 1 luồng nghiệp vụ end-to-end. Dán lệnh và kết quả. ]

curl http://<RADMIN_IP_DOI_TAC>:8000/health# kết quả: ...



VI. Kiểm thử

6.1. Chiến lược kiểm thử

[ Hướng dẫn: Nhóm dùng công cụ gì (Postman, Newman), test những loại ca nào. ]

............................................................................................................

6.2. Bộ test case

[ Hướng dẫn: Liệt kê các ca test: happy path, sai schema, sai auth, giá trị biên, lỗi nghiệp vụ. ]




 | 



STT | 



Ca kiểm thử | 



Input | 



Kết quả mong đợi


 | 



1 | 



 | 



 | 






 | 



2 | 



 | 



 | 






 | 



3 | 



 | 



 | 






 | 



4 | 



 | 



 | 





6.3. Kết quả kiểm thử

[ Hướng dẫn: Tóm tắt kết quả Newman: bao nhiêu test pass/fail. Dẫn chiếu report trong reports/. ]

............................................................................................................

6.4. Xử lý lỗi upstream

[ Hướng dẫn: Trình bày cách service xử lý khi nhóm phụ thuộc lỗi: timeout, retry, trả lỗi rõ ràng. Dán đoạn code xử lý nếu có. ]

............................................................................................................



VII. Minh chứng (Evidence)

[ Hướng dẫn: Chèn ảnh chụp màn hình và dẫn chiếu file trong thư mục reports/. Mỗi minh chứng ghi rõ chứng minh điều gì. ]




 | 



Loại minh chứng | 



Chứng minh điều gì | 



File trong reports/


 | 



Ảnh docker compose ps | 



Container chạy healthy | 






 | 



Ảnh /health | 



Service sống | 






 | 



Log xử lý input/output | 



Service có nghiệp vụ thật | 






 | 



Newman report | 



Đã kiểm thử API | 






 | 



Request/response hoặc payload MQTT mẫu | 



Tích hợp hoạt động | 






 | 



Ảnh gọi chéo qua Radmin IP | 



Tích hợp liên nhóm thật | 







VIII. Phân công công việc

[ Hướng dẫn: Bảng phân công minh bạch phục vụ chấm điểm cá nhân. Tổng % đóng góp = 100%. ]




 | 



Thành viên | 



Công việc đảm nhận | 



% đóng góp | 



Tự đánh giá


 | 



 | 



 | 



 | 






 | 



 | 



 | 



 | 






 | 



 | 



 | 



 | 






 | 



 | 



 | 



 | 







IX. Khó khăn và bài học

[ Hướng dẫn: Nêu khó khăn gặp phải (kỹ thuật, tích hợp, phối hợp) và cách giải quyết. Bài học rút ra. ]

............................................................................................................

............................................................................................................

X. Kết luận

[ Hướng dẫn: Tóm tắt service đã hoàn thành được gì, mức độ đạt mục tiêu, hướng phát triển. ]

............................................................................................................



Phụ lục A — Thông tin repo

Link repository: ____________________________

Nhánh chính: ____________________________

Hướng dẫn chạy (RUN_COMPOSE.md): có / không

Tag image: ____________________________

Lệnh chạy nhanh:

git clone <repo>cp .env.example .envdocker compose up -d --builddocker compose pscurl http://localhost:8000/health



Phụ lục B — Gợi ý nội dung nghiệp vụ theo từng service

Dùng bảng dưới để biết riêng service của nhóm cần nhấn mạnh gì ở mục II (Phân tích nghiệp vụ).

IoT Ingestion

Đầu vào: topic smart-campus/raw/iot/environment. Đầu ra: smart-campus/events/sensor.

Logic phải nêu: validate field bắt buộc, đối chiếu device_registry.csv, chuẩn hóa đơn vị, phân loại status.

Quy tắc phải có ngưỡng: danger (temp>=40, co2>=1800, smoke>=1.0), warning (temp>=35, humidity>=85, co2>=1200, smoke>=0.5, battery<20), sensor_error, invalid_device.

Nêu rõ ĐÃ LOẠI BỎ field scenario_hint_for_teacher và không dùng nó trong logic.

Access Gate

Đầu vào: smart-campus/raw/access/rfid-uid. Đầu ra: smart-campus/events/access.

Logic: validate, đối chiếu uid_whitelist.csv, quyết định granted/denied, enrich student_id/full_name/class_name.

Quy tắc: UID có trong whitelist → granted; UID lạ → denied + thông tin null. Ghi log mọi lượt.

Nêu cách đọc whitelist từ file, không hard-code.

Camera Stream

Đầu vào: MJPEG stream. Đầu ra: REST sang AI Vision + MQTT events/camera sang Analytics.

Logic: kiểm tra frame, phát hiện motion (frame difference), throttle/cooldown, tiền xử lý, đóng gói request.

Quy tắc: không motion → không gọi AI; có motion → gửi 1 snapshot rồi cooldown. Nêu ngưỡng motion và cooldown.

AI Vision

Đầu vào: REST POST /api/v1/detect. Đầu ra: response có detections, confidence, risk_level.

Logic: tải ảnh, chạy model (thật/mock), lọc theo confidence, đánh giá risk_level theo ngữ cảnh.

Quy tắc: ngưỡng confidence, công thức risk_level. Khai báo rõ nếu dùng mock.

Core Business

Đầu vào: events/sensor, events/access, events/camera (MQTT) + REST tới AI Vision/Access. Đầu ra: alert sang Notification + events cho Analytics.

Logic: áp policy, kết hợp nhiều event, quyết định severity, tạo alert, lưu audit.

Quy tắc: liệt kê bộ luật (nhiều rule), nêu cơ chế chống cảnh báo trùng. Đây là service trọng yếu, viết kỹ nhất.

Notification

Đầu vào: alert từ Core (MQTT). Đầu ra: kênh thật (Telegram/email/webhook).

Logic: định tuyến theo target+severity, chọn kênh, gửi, retry, ghi trạng thái.

Quy tắc: bảng định tuyến theo mức độ, chính sách retry, chống gửi trùng.

Analytics

Đầu vào: mọi topic events (MQTT). Đầu ra: REST endpoint KPI cho dashboard.

Logic: thu thập, tổng hợp (trung bình/đếm), phân tích xu hướng, đóng gói báo cáo.

Quy tắc: tổng hợp theo phòng/giờ/loại, phân theo severity. Không trả dữ liệu thô.

