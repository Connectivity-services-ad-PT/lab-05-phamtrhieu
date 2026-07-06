"""
Notification Service – FIT4110 Smart Campus Operations Platform
team-notify

Trách nhiệm nghiệp vụ:
  - Subscribe MQTT topic nhận alert từ Core Business
  - ROUTE: định tuyến đúng người nhận theo target + severity
  - PICK CHANNEL: chọn kênh gửi theo mức độ
      critical  → Telegram + Email (tối thiểu 2 kênh)
      high      → Telegram
      medium    → Email
      low       → chỉ log, không gửi
  - SEND: gửi thật qua Telegram Bot API và/hoặc SMTP
  - RETRY: retry tối đa MAX_RETRY lần, delay tăng dần
  - RECORD: ghi lại trạng thái gửi mỗi alert vào DB + memory
  - Deduplication: cùng alert_id không gửi lại trong DEDUP_WINDOW giây
  - REST endpoint /health và /notification-logs để kiểm tra
"""

import asyncio
import json
import logging
import os
import smtplib
import ssl
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List, Optional

import httpx
import paho.mqtt.client as mqtt
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from dotenv import load_dotenv
load_dotenv()

# Cấu hình từ biến môi trường
SERVICE_NAME = os.getenv("SERVICE_NAME", "team-notify")

# ──────────────────────────────────────────────
# Cấu hình từ biến môi trường
# ──────────────────────────────────────────────
SERVICE_NAME = os.getenv("SERVICE_NAME", "team-notify")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "1.0.0")

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_ALERT_TOPIC = os.getenv("MQTT_ALERT_TOPIC", "smart-campus/events/alert")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")          # dành cho security_team
TELEGRAM_ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")  # dành cho admin

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_SECURITY_TEAM = os.getenv("EMAIL_SECURITY_TEAM", "")
EMAIL_ADMIN = os.getenv("EMAIL_ADMIN", "")

MAX_RETRY = int(os.getenv("MAX_RETRY", "3"))
RETRY_DELAY_BASE = float(os.getenv("RETRY_DELAY_BASE", "2.0"))   # giây, tăng gấp đôi mỗi lần
DEDUP_WINDOW = int(os.getenv("DEDUP_WINDOW", "300"))              # giây chống gửi trùng

# ──────────────────────────────────────────────
# Logger
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("notification-service")

# ──────────────────────────────────────────────
# Bộ nhớ runtime (thay thế DB trong demo)
# ──────────────────────────────────────────────
NOTIFICATION_LOGS: List[Dict] = []   # bản ghi trạng thái gửi
DEDUP_SEEN: Dict[str, float] = {}    # alert_id → epoch khi nhận đầu tiên


# ──────────────────────────────────────────────
# Pydantic models
# ──────────────────────────────────────────────
class AlertEvent(BaseModel):
    event_type: str
    source_service: str
    alert_id: str
    alert_type: str
    severity: str           # critical / high / medium / low
    message: str
    origin_event_id: Optional[str] = None
    target: Optional[str] = "all"   # security_team / admin / all
    timestamp: str


class NotificationLog(BaseModel):
    log_id: str
    alert_id: str
    severity: str
    target: str
    channel: str            # telegram / email / log_only
    recipient: str
    status: str             # sent / failed / skipped
    attempts: int
    sent_at: Optional[str] = None
    error: Optional[str] = None


# ──────────────────────────────────────────────
# Routing table: (target, severity) → [channels]
# ──────────────────────────────────────────────
def get_routing(severity: str, target: str) -> List[Dict]:
    """
    Trả về danh sách dict {channel, recipient} dựa theo severity + target.
    Quy tắc:
      critical → telegram + email cho đúng target (tối thiểu 2 kênh)
      high     → telegram cho đúng target
      medium   → email cho đúng target
      low      → log_only
    """
    severity = severity.lower()
    target = (target or "all").lower()

    # Xác định chat_id và email theo target
    if target == "security_team":
        tg_chat = TELEGRAM_CHAT_ID
        mail = EMAIL_SECURITY_TEAM
    elif target == "admin":
        tg_chat = TELEGRAM_ADMIN_CHAT_ID
        mail = EMAIL_ADMIN
    else:  # "all" hoặc unknown → gửi cả hai nhóm
        tg_chat = TELEGRAM_CHAT_ID or TELEGRAM_ADMIN_CHAT_ID
        mail = EMAIL_SECURITY_TEAM or EMAIL_ADMIN

    routes = []
    if severity == "critical":
        if tg_chat:
            routes.append({"channel": "telegram", "recipient": tg_chat})
        if mail:
            routes.append({"channel": "email", "recipient": mail})
        # đảm bảo tối thiểu 2 kênh nếu chỉ có 1 kênh được cấu hình
        if len(routes) < 2:
            logger.warning(
                "critical alert nhưng chỉ có %d kênh được cấu hình (cần ≥ 2)", len(routes)
            )
    elif severity == "high":
        if tg_chat:
            routes.append({"channel": "telegram", "recipient": tg_chat})
        elif mail:
            routes.append({"channel": "email", "recipient": mail})
    elif severity == "medium":
        if mail:
            routes.append({"channel": "email", "recipient": mail})
        elif tg_chat:
            routes.append({"channel": "telegram", "recipient": tg_chat})
    else:
        # low → chỉ log, không gửi
        routes.append({"channel": "log_only", "recipient": "console"})

    return routes if routes else [{"channel": "log_only", "recipient": "console"}]


# ──────────────────────────────────────────────
# Gửi Telegram
# ──────────────────────────────────────────────
async def send_telegram(chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"})
        resp.raise_for_status()


# ──────────────────────────────────────────────
# Gửi Email
# ──────────────────────────────────────────────
def send_email_sync(to_addr: str, subject: str, body: str) -> None:
    """Gửi email qua SMTP (chạy trong thread để không block event loop)."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = to_addr
    msg.attach(MIMEText(body, "plain", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls(context=context)
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, to_addr, msg.as_string())


async def send_email(to_addr: str, subject: str, body: str) -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, send_email_sync, to_addr, subject, body)


# ──────────────────────────────────────────────
# Dispatcher với retry
# ──────────────────────────────────────────────
async def dispatch_channel(alert: AlertEvent, channel: str, recipient: str) -> NotificationLog:
    """Gửi qua một kênh, retry MAX_RETRY lần với backoff, trả về log."""
    log_id = str(uuid.uuid4())[:8]
    attempts = 0
    last_error = None

    subject = f"[SmartCampus] {alert.severity.upper()} – {alert.alert_type}"
    body = (
        f"Alert ID : {alert.alert_id}\n"
        f"Type     : {alert.alert_type}\n"
        f"Severity : {alert.severity}\n"
        f"Location : (xem origin_event_id={alert.origin_event_id})\n"
        f"Time     : {alert.timestamp}\n\n"
        f"{alert.message}"
    )
    tg_text = (
        f"🚨 <b>[{alert.severity.upper()}]</b> {alert.alert_type}\n"
        f"📍 <i>{alert.message}</i>\n"
        f"🕐 {alert.timestamp}\n"
        f"🆔 {alert.alert_id}"
    )

    if channel == "log_only":
        logger.info("[LOW] alert=%s message=%s (no send)", alert.alert_id, alert.message)
        return NotificationLog(
            log_id=log_id,
            alert_id=alert.alert_id,
            severity=alert.severity,
            target=alert.target or "all",
            channel="log_only",
            recipient="console",
            status="skipped",
            attempts=0,
            sent_at=now_iso(),
        )

    for attempt in range(1, MAX_RETRY + 1):
        attempts = attempt
        try:
            if channel == "telegram":
                if not TELEGRAM_BOT_TOKEN:
                    raise RuntimeError("TELEGRAM_BOT_TOKEN chưa được cấu hình")
                await send_telegram(recipient, tg_text)
            elif channel == "email":
                if not SMTP_USER:
                    raise RuntimeError("SMTP_USER chưa được cấu hình")
                await send_email(recipient, subject, body)
            else:
                raise ValueError(f"Kênh không hỗ trợ: {channel}")

            logger.info(
                "✅ Gửi thành công | alert=%s channel=%s attempt=%d",
                alert.alert_id, channel, attempt,
            )
            return NotificationLog(
                log_id=log_id,
                alert_id=alert.alert_id,
                severity=alert.severity,
                target=alert.target or "all",
                channel=channel,
                recipient=recipient,
                status="sent",
                attempts=attempts,
                sent_at=now_iso(),
            )
        except Exception as exc:
            last_error = str(exc)
            logger.warning(
                "⚠️ Gửi thất bại | alert=%s channel=%s attempt=%d/%d error=%s",
                alert.alert_id, channel, attempt, MAX_RETRY, last_error,
            )
            if attempt < MAX_RETRY:
                delay = RETRY_DELAY_BASE * (2 ** (attempt - 1))   # exponential backoff
                await asyncio.sleep(delay)

    logger.error(
        "❌ Hết retry | alert=%s channel=%s error=%s",
        alert.alert_id, channel, last_error,
    )
    return NotificationLog(
        log_id=log_id,
        alert_id=alert.alert_id,
        severity=alert.severity,
        target=alert.target or "all",
        channel=channel,
        recipient=recipient,
        status="failed",
        attempts=attempts,
        error=last_error,
    )


# ──────────────────────────────────────────────
# Xử lý 1 alert (dedup + route + send)
# ──────────────────────────────────────────────
async def process_alert(payload: Dict) -> None:
    # 1. Parse
    try:
        alert = AlertEvent(**payload)
    except Exception as exc:
        logger.error("Schema không hợp lệ, bỏ qua: %s | payload=%s", exc, payload)
        return

    # 2. Deduplication
    now = time.time()
    if alert.alert_id in DEDUP_SEEN:
        elapsed = now - DEDUP_SEEN[alert.alert_id]
        if elapsed < DEDUP_WINDOW:
            logger.info(
                "🔁 Trùng alert_id=%s (đã xử lý %.0fs trước), bỏ qua",
                alert.alert_id, elapsed,
            )
            return
    DEDUP_SEEN[alert.alert_id] = now

    logger.info(
        "📩 Nhận alert | id=%s type=%s severity=%s target=%s",
        alert.alert_id, alert.alert_type, alert.severity, alert.target,
    )

    # 3. Routing
    routes = get_routing(alert.severity, alert.target or "all")

    # 4. Gửi song song tất cả kênh
    tasks = [dispatch_channel(alert, r["channel"], r["recipient"]) for r in routes]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 5. Ghi log
    for result in results:
        if isinstance(result, Exception):
            logger.error("Lỗi không mong đợi khi gửi: %s", result)
        else:
            NOTIFICATION_LOGS.append(result.model_dump())


# ──────────────────────────────────────────────
# MQTT client
# ──────────────────────────────────────────────
mqtt_client: Optional[mqtt.Client] = None


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("✅ Kết nối MQTT broker %s:%d", MQTT_BROKER, MQTT_PORT)
        client.subscribe(MQTT_ALERT_TOPIC)
        logger.info("📡 Subscribe topic: %s", MQTT_ALERT_TOPIC)
    else:
        logger.error("❌ Kết nối MQTT thất bại rc=%d", rc)


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except json.JSONDecodeError as exc:
        logger.error("Payload không phải JSON: %s | raw=%s", exc, msg.payload[:200])
        return

    # Đẩy vào event loop của FastAPI để xử lý async
    loop = userdata.get("loop")
    if loop and loop.is_running():
        asyncio.run_coroutine_threadsafe(process_alert(payload), loop)
    else:
        logger.warning("Event loop chưa sẵn sàng, bỏ qua message")


def on_disconnect(client, userdata, rc):
    if rc != 0:
        logger.warning("MQTT mất kết nối rc=%d, sẽ reconnect tự động", rc)


def start_mqtt(loop: asyncio.AbstractEventLoop) -> None:
    global mqtt_client
    mqtt_client = mqtt.Client(userdata={"loop": loop})
    if MQTT_USERNAME:
        mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.on_disconnect = on_disconnect
    mqtt_client.reconnect_delay_set(min_delay=1, max_delay=30)
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        mqtt_client.loop_start()
    except Exception as exc:
        logger.error("Không thể kết nối MQTT: %s", exc)


# ──────────────────────────────────────────────
# FastAPI lifespan
# ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_event_loop()
    start_mqtt(loop)
    logger.info("🚀 Notification Service khởi động | broker=%s topic=%s", MQTT_BROKER, MQTT_ALERT_TOPIC)
    yield
    if mqtt_client:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
    logger.info("Notification Service dừng.")


# ──────────────────────────────────────────────
# FastAPI app
# ──────────────────────────────────────────────
app = FastAPI(
    title="FIT4110 – Notification Service",
    version=SERVICE_VERSION,
    description="Định tuyến cảnh báo từ Core Business đến đúng người, đúng kênh, có retry.",
    lifespan=lifespan,
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "mqtt_connected": mqtt_client.is_connected() if mqtt_client else False,
        "total_logs": len(NOTIFICATION_LOGS),
    }


@app.get("/notification-logs")
def get_logs(
    limit: int = Query(default=50, ge=1, le=500),
    status: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
):
    """Trả về danh sách log gửi thông báo, lọc theo status và severity."""
    items = NOTIFICATION_LOGS
    if status:
        items = [i for i in items if i["status"] == status]
    if severity:
        items = [i for i in items if i["severity"] == severity]
    return {"total": len(items), "items": items[-limit:]}


@app.post("/test-alert", status_code=202)
async def test_alert(alert: AlertEvent):
    """
    Endpoint để kiểm thử thủ công (Postman/Newman).
    Gửi alert trực tiếp vào pipeline xử lý mà không qua MQTT.
    """
    await process_alert(alert.model_dump())
    return {"accepted": True, "alert_id": alert.alert_id}