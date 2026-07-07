import os
import uuid
import requests
import psycopg2
from datetime import datetime, timezone
from typing import Dict, List, Optional
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

SERVICE_NAME = os.getenv("SERVICE_NAME", "notification-service")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.5.0")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "local-dev-token")

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_USER = os.getenv("POSTGRES_USER", "lab05")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "lab05pass")
POSTGRES_DB = os.getenv("POSTGRES_DB", "notificationdb")

AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://ai-service:9000")


app = FastAPI(
    title="FIT4110 Lab 05 - Notification Service",
    version=SERVICE_VERSION,
    description="Notification Service API with PostgreSQL and AI integration.",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# In-memory storage fallback if DB is not available
IN_MEMORY_NOTIFICATIONS = {}

def get_db_connection():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        connect_timeout=3
    )

def execute_db_query(query, params=None, fetch=False):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(query, params or ())
        if fetch:
            results = cur.fetchall()
            cur.close()
            conn.close()
            return results
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB Warning] SQL Execution failed, falling back to memory: {e}")
        return None

import os
import uuid
import requests
import psycopg2
import threading
import queue
import time
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from typing import Dict, List, Optional
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import paho.mqtt.client as mqtt

SERVICE_NAME = os.getenv("SERVICE_NAME", "notification-service")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.5.0")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "local-dev-token")

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_USER = os.getenv("POSTGRES_USER", "lab05")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "lab05pass")
POSTGRES_DB = os.getenv("POSTGRES_DB", "notificationdb")

AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://ai-service:9000")

# MQTT Broker Configuration
MQTT_BROKER = os.getenv("MQTT_BROKER", "broker.hivemq.com")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "smart-campus/events/alert")

# Deduplication cache
ALERT_DEDUPLICATION_CACHE = {}

# Background worker queue and classes
DISPATCH_QUEUE = queue.Queue()

class DispatchJob:
    def __init__(self, delivery_id: str, alert_id: str, event_id: str, channel: str, recipient: str, title: str, message: str, severity: str):
        self.delivery_id = delivery_id
        self.alert_id = alert_id
        self.event_id = event_id
        self.channel = channel
        self.recipient = recipient
        self.title = title
        self.message = message
        self.severity = severity
        self.retries = 0

app = FastAPI(
    title="FIT4110 Lab 05 - Notification Service",
    version=SERVICE_VERSION,
    description="Notification Service API with PostgreSQL and AI integration.",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage fallback if DB is not available
IN_MEMORY_NOTIFICATIONS = {}

def get_db_connection():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        connect_timeout=3
    )

def execute_db_query(query, params=None, fetch=False):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(query, params or ())
        if fetch:
            results = cur.fetchall()
            cur.close()
            conn.close()
            return results
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB Warning] SQL Execution failed, falling back to memory: {e}")
        return None

def update_db_attempt(delivery_id: str, status_str: str, attempt_time: str, retries: int):
    query = """
    UPDATE notifications 
    SET status = %s, last_attempt_at = %s, retry_count = %s 
    WHERE delivery_id = %s;
    """
    res = execute_db_query(query, (status_str, attempt_time, retries, delivery_id))
    if not res:
        if delivery_id in IN_MEMORY_NOTIFICATIONS:
            IN_MEMORY_NOTIFICATIONS[delivery_id]["status"] = status_str
            IN_MEMORY_NOTIFICATIONS[delivery_id]["lastAttemptAt"] = attempt_time
            IN_MEMORY_NOTIFICATIONS[delivery_id]["retryCount"] = retries

def update_db_status(delivery_id: str, status_str: str, delivered_at: Optional[str], error_msg: Optional[str]):
    query = """
    UPDATE notifications 
    SET status = %s, delivered_at = %s, error_message = %s 
    WHERE delivery_id = %s;
    """
    res = execute_db_query(query, (status_str, delivered_at, error_msg, delivery_id))
    if not res:
        if delivery_id in IN_MEMORY_NOTIFICATIONS:
            IN_MEMORY_NOTIFICATIONS[delivery_id]["status"] = status_str
            IN_MEMORY_NOTIFICATIONS[delivery_id]["deliveredAt"] = delivered_at
            IN_MEMORY_NOTIFICATIONS[delivery_id]["errorMessage"] = error_msg

def is_duplicate_alert(alert_id: str) -> bool:
    now = datetime.now(timezone.utc)
    for aid, ts in list(ALERT_DEDUPLICATION_CACHE.items()):
        if (now - ts).total_seconds() > 300:
            ALERT_DEDUPLICATION_CACHE.pop(aid, None)
            
    if alert_id in ALERT_DEDUPLICATION_CACHE:
        print(f"[Deduplication Info] Alert {alert_id} is a duplicate (memory check)")
        return True
        
    query = """
    SELECT sent_at FROM notifications 
    WHERE alert_id = %s 
    ORDER BY sent_at DESC 
    LIMIT 1;
    """
    rows = execute_db_query(query, (alert_id,), fetch=True)
    if rows:
        try:
            last_sent_str = rows[0][0]
            last_sent = datetime.fromisoformat(last_sent_str)
            if (now - last_sent).total_seconds() <= 300:
                print(f"[Deduplication Info] Alert {alert_id} is a duplicate (DB check)")
                ALERT_DEDUPLICATION_CACHE[alert_id] = last_sent
                return True
        except Exception as e:
            print(f"[Deduplication Warning] Failed parsing sent_at: {e}")
            
    ALERT_DEDUPLICATION_CACHE[alert_id] = now
    return False

def resolve_channels_and_recipients(severity: str, target: str, requested_channels: Optional[List[str]]) -> List[str]:
    severity_upper = severity.upper()
    if severity_upper == "LOW":
        return []
        
    if requested_channels:
        if severity_upper == "CRITICAL" and len(requested_channels) < 2:
            channels_set = set(requested_channels)
            for c in ["telegram", "email", "app"]:
                channels_set.add(c)
                if len(channels_set) >= 2:
                    break
            return list(channels_set)
        return requested_channels

    if severity_upper == "CRITICAL":
        return ["telegram", "email", "app"]
    elif severity_upper == "HIGH":
        return ["telegram", "app"]
    elif severity_upper == "MEDIUM":
        return ["email"]
    else:
        return ["app"]

def get_channel_recipients(target: str, channel: str) -> str:
    target_lower = (target or "").lower()
    if channel == "email":
        if "security" in target_lower:
            return "security-team@campus.local"
        elif "admin" in target_lower:
            return "admin-office@campus.local"
        else:
            return os.getenv("EMAIL_TO", "info@campus.local")
    elif channel == "telegram":
        if "security" in target_lower:
            return os.getenv("TELEGRAM_CHAT_ID_SECURITY") or os.getenv("TELEGRAM_CHAT_ID", "default_chat")
        else:
            return os.getenv("TELEGRAM_CHAT_ID", "default_chat")
    return "default"

def send_telegram(chat_id: str, title: str, message: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token or not chat_id or chat_id == "default_chat":
        print("[Telegram Mock] Bot credentials not configured. Executing mock webhook POST.")
        url = "https://httpbin.org/post"
        payload = {"channel": "telegram", "chat_id": chat_id, "title": title, "message": message}
        try:
            r = requests.post(url, json=payload, timeout=5)
            return r.status_code == 200
        except Exception as e:
            print(f"[Telegram Mock Error] HTTP call failed: {e}")
            return False
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": f"🚨 *{title}*\n{message}",
        "parse_mode": "Markdown"
    }
    try:
        r = requests.post(url, json=payload, timeout=5)
        if r.status_code == 200:
            print(f"[Telegram Info] Notification sent successfully to Chat {chat_id}")
            return True
        else:
            print(f"[Telegram Error] API failed: {r.text}")
            return False
    except Exception as e:
        print(f"[Telegram Error] HTTP call failed: {e}")
        return False

def send_email(recipient: str, title: str, message: str) -> bool:
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    email_from = os.getenv("EMAIL_FROM", "sender@example.com")
    
    if not smtp_server or not smtp_user or not smtp_password:
        print("[Email Mock] SMTP credentials not configured. Executing mock webhook POST.")
        url = "https://httpbin.org/post"
        payload = {"channel": "email", "recipient": recipient, "title": title, "message": message}
        try:
            r = requests.post(url, json=payload, timeout=5)
            return r.status_code == 200
        except Exception as e:
            print(f"[Email Mock Error] HTTP call failed: {e}")
            return False
        
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = title
        msg["From"] = email_from
        msg["To"] = recipient
        
        html_body = f"""
        <html>
          <body style="font-family: 'Outfit', sans-serif; color: #0f172a; margin: 0; padding: 20px;">
            <div style="max-width: 600px; margin: auto; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
              <div style="background-color: #eb5e00; padding: 20px; color: white; font-weight: bold; font-size: 20px;">
                DNU Smart Campus Alert
              </div>
              <div style="padding: 24px;">
                <h2 style="color: #eb5e00; margin-top: 0;">{title}</h2>
                <p style="font-size: 16px; line-height: 1.6;">{message}</p>
                <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 20px 0;">
                <p style="font-size: 12px; color: #64748b;">This is an automated system alert from DNU Operations Platform.</p>
              </div>
            </div>
          </body>
        </html>
        """
        msg.attach(MIMEText(message, "plain"))
        msg.attach(MIMEText(html_body, "html"))
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(email_from, recipient, msg.as_string())
        server.quit()
        print(f"[Email Info] Notification sent successfully to {recipient}")
        return True
    except Exception as e:
        print(f"[Email Error] SMTP failed to send to {recipient}: {e}")
        return False

def send_webhook(title: str, message: str) -> bool:
    webhook_url = os.getenv("WEBHOOK_URL")
    if not webhook_url:
        print("[Webhook Warning] Webhook URL not configured.")
        return True
        
    try:
        payload = {
            "title": title,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        r = requests.post(webhook_url, json=payload, timeout=5)
        if r.status_code in [200, 201, 202]:
            print(f"[Webhook Info] Webhook notification sent successfully to {webhook_url}")
            return True
        else:
            print(f"[Webhook Error] API failed: status {r.status_code}")
            return False
    except Exception as e:
        print(f"[Webhook Error] Failed to send webhook: {e}")
        return False

def process_dispatch_job(job: DispatchJob):
    attempt_time = datetime.now(timezone.utc).isoformat()
    update_db_attempt(job.delivery_id, "sending", attempt_time, job.retries)
    
    success = False
    if job.channel == "telegram":
        success = send_telegram(job.recipient, job.title, job.message)
    elif job.channel == "email":
        success = send_email(job.recipient, job.title, job.message)
    elif job.channel == "webhook" or job.channel == "app":
        success = send_webhook(job.title, job.message)
    else:
        success = send_webhook(job.title, f"[{job.channel.upper()}] {job.message}")
        
    if success:
        delivered_time = datetime.now(timezone.utc).isoformat()
        update_db_status(job.delivery_id, "delivered", delivered_time, "No error")
    else:
        job.retries += 1
        if job.retries <= 3:
            print(f"[Worker Warning] Job {job.delivery_id} failed on channel {job.channel}. Retrying {job.retries}/3 in 5 seconds...")
            time.sleep(5)
            DISPATCH_QUEUE.put(job)
        else:
            update_db_status(job.delivery_id, "failed", None, "Max retries reached")

def run_dispatch_worker():
    while True:
        job = DISPATCH_QUEUE.get()
        if job is None:
            break
        try:
            process_dispatch_job(job)
        except Exception as e:
            print(f"[Worker Error] Failed executing job: {e}")
        finally:
            DISPATCH_QUEUE.task_done()

def log_notification_delivery(delivery_id: str, alert_id: str, event_id: str, channel: str, status_str: str, sent_at: str):
    insert_query = """
    INSERT INTO notifications (delivery_id, alert_id, event_id, channel, status, sent_at, delivered_at, error_message, retry_count, last_attempt_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
    """
    res = execute_db_query(insert_query, (delivery_id, alert_id, event_id, channel, status_str, sent_at, None, None, 0, sent_at))
    if not res:
        IN_MEMORY_NOTIFICATIONS[delivery_id] = {
            "deliveryId": delivery_id,
            "alertId": alert_id,
            "eventId": event_id,
            "channel": channel,
            "status": status_str,
            "sentAt": sent_at,
            "deliveredAt": None,
            "errorMessage": None,
            "retryCount": 0,
            "lastAttemptAt": sent_at
        }

def trigger_notification_dispatch(
    event_id: str,
    alert_id: str,
    severity: str,
    title: str,
    message: str,
    source: str,
    target: str,
    channels: Optional[List[str]]
):
    sent_at = datetime.now(timezone.utc).isoformat()
    
    if is_duplicate_alert(alert_id):
        delivery_id = str(uuid.uuid4())
        log_notification_delivery(
            delivery_id=delivery_id,
            alert_id=alert_id,
            event_id=event_id,
            channel="system",
            status_str="duplicate",
            sent_at=sent_at
        )
        return
        
    resolved_channels = resolve_channels_and_recipients(severity, target, channels)
    
    if not resolved_channels:
        delivery_id = str(uuid.uuid4())
        log_notification_delivery(
            delivery_id=delivery_id,
            alert_id=alert_id,
            event_id=event_id,
            channel="log",
            status_str="logged",
            sent_at=sent_at
        )
        print(f"[Logging Info] LOW severity alert logged: ID={alert_id}, Title={title}, Message={message}")
        return
        
    for channel in resolved_channels:
        delivery_id = str(uuid.uuid4())
        recipient = get_channel_recipients(target, channel)
        
        log_notification_delivery(
            delivery_id=delivery_id,
            alert_id=alert_id,
            event_id=event_id,
            channel=channel,
            status_str="pending",
            sent_at=sent_at
        )
        
        job = DispatchJob(
            delivery_id=delivery_id,
            alert_id=alert_id,
            event_id=event_id,
            channel=channel,
            recipient=recipient,
            title=title,
            message=message,
            severity=severity
        )
        DISPATCH_QUEUE.put(job)

def process_incoming_alert(data: dict):
    event_id = data.get("eventId") or data.get("event_id") or str(uuid.uuid4())
    alert_id = data.get("alertId") or data.get("alert_id") or f"ALT-{int(datetime.now(timezone.utc).timestamp())}"
    severity = (data.get("severity") or "MEDIUM").upper()
    
    inner_payload = data.get("payload") or data.get("data") or {}
    if isinstance(inner_payload, dict):
        title = inner_payload.get("title") or data.get("title") or "Cảnh báo"
        message = inner_payload.get("message") or data.get("message") or "Phát hiện sự cố"
        source = inner_payload.get("source") or data.get("source") or "unknown"
        target = data.get("target") or inner_payload.get("target") or "all"
    else:
        title = data.get("title") or "Cảnh báo"
        message = data.get("message") or "Phát hiện sự cố"
        source = data.get("source") or "unknown"
        target = data.get("target") or "all"
        
    channels = data.get("channels")
    
    trigger_notification_dispatch(
        event_id=event_id,
        alert_id=alert_id,
        severity=severity,
        title=title,
        message=message,
        source=source,
        target=target,
        channels=channels
    )

def on_mqtt_message(client, userdata, msg):
    try:
        payload_str = msg.payload.decode('utf-8')
        print(f"[MQTT Info] Message received on topic {msg.topic}: {payload_str}")
        payload_data = json.loads(payload_str)
        process_incoming_alert(payload_data)
    except Exception as e:
        print(f"[MQTT Error] Failed to process incoming MQTT message: {e}")

def run_mqtt_client():
    client_id = f"notify-service-{uuid.uuid4().hex[:6]}"
    client = mqtt.Client(client_id=client_id)
    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    
    client.on_message = on_mqtt_message
    
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print(f"[MQTT Info] Connected to broker {MQTT_BROKER}:{MQTT_PORT}")
            client.subscribe(MQTT_TOPIC)
            print(f"[MQTT Info] Subscribed to topic: {MQTT_TOPIC}")
        else:
            print(f"[MQTT Error] Connect failed with code {rc}")
            
    client.on_connect = on_connect
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        client.loop_forever()
    except Exception as e:
        print(f"[MQTT Error] Failed to run MQTT client: {e}")

def start_mqtt_background_thread():
    t = threading.Thread(target=run_mqtt_client, daemon=True)
    t.start()

def start_dispatch_worker_thread():
    t = threading.Thread(target=run_dispatch_worker, daemon=True)
    t.start()

@app.on_event("startup")
def startup_event():
    create_table_query = """
    CREATE TABLE IF NOT EXISTS notifications (
        delivery_id VARCHAR(50) PRIMARY KEY,
        alert_id VARCHAR(100) NOT NULL,
        event_id VARCHAR(50) NOT NULL,
        channel VARCHAR(50) NOT NULL,
        status VARCHAR(50) NOT NULL,
        sent_at VARCHAR(50) NOT NULL,
        delivered_at VARCHAR(50),
        error_message TEXT,
        retry_count INTEGER DEFAULT 0,
        last_attempt_at VARCHAR(50)
    );
    """
    res = execute_db_query(create_table_query)
    if res:
        print("[DB Info] Table 'notifications' successfully initialized in PostgreSQL.")
        # Ensure schema modifications (ADD COLUMN IF NOT EXISTS) are executed in case table already exists
        execute_db_query("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0;")
        execute_db_query("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS last_attempt_at VARCHAR(50);")
    else:
        print("[DB Info] Table initialization failed, running with memory fallback.")
        
    # Start background threads
    start_mqtt_background_thread()
    start_dispatch_worker_thread()
    print("[Startup Info] Background MQTT listener and Dispatch worker started successfully.")


# Pydantic schemas
class AlertData(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=1000)
    source: str = Field(..., min_length=1, max_length=100)
    alertLevel: Optional[str] = Field(default=None, max_length=50)

class AlertEventPayload(BaseModel):
    eventId: str
    eventType: str
    alertId: str = Field(..., min_length=1, max_length=100)
    correlationId: str = Field(..., min_length=1, max_length=100)
    source: Optional[str] = None
    severity: str
    alertVersion: Optional[int] = Field(default=1, ge=1)
    occurredAt: Optional[str] = None
    payload: Optional[AlertData] = None  # Mapping legacy postman field
    data: Optional[AlertData] = None     # Mapping standard schema field
    channels: Optional[List[str]] = Field(default=None, max_length=4)
    metadata: Optional[dict] = None

class AIVisionAlertPayload(BaseModel):
    source: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=1000)
    severity: str = Field(..., min_length=1, max_length=50)
    data: Optional[dict] = None

class NotificationDelivery(BaseModel):
    deliveryId: str
    alertId: str
    eventId: str
    channel: str
    status: str
    sentAt: str
    deliveredAt: Optional[str] = None
    errorMessage: Optional[str] = None

# RFC 7807 problem builder
def build_problem(
    status_code: int,
    title: str,
    detail: str,
    instance: Optional[str] = None,
    problem_type: str = "about:blank",
):
    problem = {
        "type": problem_type,
        "title": title,
        "status": status_code,
        "detail": detail,
    }
    if instance:
        problem["instance"] = instance
    return problem

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        problem = exc.detail
    else:
        problem = build_problem(
            status_code=exc.status_code,
            title="HTTP Error",
            detail=str(exc.detail),
            instance=str(request.url.path),
        )
    return JSONResponse(
        status_code=exc.status_code,
        content=problem,
        media_type="application/problem+json",
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    first_error = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(item) for item in first_error.get("loc", []))
    message = first_error.get("msg", "Validation error")
    detail = f"{location}: {message}" if location else message

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=build_problem(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="Unprocessable Entity",
            detail=detail,
            instance=str(request.url.path),
            problem_type="https://notification.campus.local/problems/unprocessable-entity",
        ),
        media_type="application/problem+json",
    )

def verify_bearer_token(authorization: Optional[str] = Header(default=None)) -> None:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=build_problem(
                status_code=status.HTTP_401_UNAUTHORIZED,
                title="Unauthorized",
                detail="Missing Authorization header",
                problem_type="https://notification.campus.local/problems/unauthorized",
            ),
        )
    expected = f"Bearer {AUTH_TOKEN}"
    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=build_problem(
                status_code=status.HTTP_401_UNAUTHORIZED,
                title="Unauthorized",
                detail="Invalid bearer token",
                problem_type="https://notification.campus.local/problems/unauthorized",
            ),
        )

# Helper to log notifications
def log_notification_delivery(delivery_id: str, alert_id: str, event_id: str, channel: str, status_str: str, sent_at: str):
    insert_query = """
    INSERT INTO notifications (delivery_id, alert_id, event_id, channel, status, sent_at, delivered_at, error_message)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
    """
    res = execute_db_query(insert_query, (delivery_id, alert_id, event_id, channel, status_str, sent_at, sent_at, "No error"))
    if not res:
        # Memory fallback
        IN_MEMORY_NOTIFICATIONS[delivery_id] = {
            "deliveryId": delivery_id,
            "alertId": alert_id,
            "eventId": event_id,
            "channel": channel,
            "status": status_str,
            "sentAt": sent_at,
            "deliveredAt": sent_at,
            "errorMessage": "No error"
        }

@app.get("/", response_class=HTMLResponse)
def root():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "dashboard.html")
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except Exception as e:
        return HTMLResponse(content=f"<h3>Error loading dashboard: {e}</h3>", status_code=500)


@app.get("/health")
def health() -> dict:
    db_ok = False
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        db_ok = True
    except Exception as e:
        print(f"[Health] DB check failed: {e}")

    ai_ok = False
    try:
        r = requests.get(f"{AI_SERVICE_URL}/health", timeout=2.0)
        if r.status_code == 200:
            ai_ok = True
    except Exception as e:
        print(f"[Health] AI check failed: {e}")

    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dependencies": {
            "database": "ok" if db_ok else "failed (memory fallback active)",
            "ai_service": "ok" if ai_ok else "failed"
        }
    }

@app.post(
    "/events/alert.created",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(verify_bearer_token)],
)
def handle_alert_created(payload: AlertEventPayload):
    try:
        uuid.UUID(payload.eventId)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=build_problem(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                title="Unprocessable Entity",
                detail="eventId must be a valid UUID",
                problem_type="https://notification.campus.local/problems/unprocessable-entity",
            ),
        )

    # Perform integration check by calling AI-service
    ai_prediction = None
    try:
        r = requests.post(f"{AI_SERVICE_URL}/predict", json={}, timeout=2.0)
        if r.status_code == 200:
            ai_prediction = r.json()
            print(f"[AI Info] Classification prediction: {ai_prediction}")
    except Exception as e:
        print(f"[AI Warning] Could not connect to AI service: {e}")

    # Check channels size boundary
    if payload.channels and len(payload.channels) > 4:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=build_problem(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                title="Unprocessable Entity",
                detail="Max 4 channels allowed",
                problem_type="https://notification.campus.local/problems/unprocessable-entity",
            ),
        )

    sent_at = datetime.now(timezone.utc).isoformat()
    
    # Extract payload details
    inner_payload = payload.payload or payload.data
    title = inner_payload.title if inner_payload else "Cảnh báo mới"
    message = inner_payload.message if inner_payload else "Phát hiện sự cố"
    source = payload.source or (inner_payload.source if inner_payload else "unknown")
    target = "all"
    if payload.metadata and isinstance(payload.metadata, dict):
        target = payload.metadata.get("target", "all")

    trigger_notification_dispatch(
        event_id=payload.eventId,
        alert_id=payload.alertId,
        severity=payload.severity,
        title=title,
        message=message,
        source=source,
        target=target,
        channels=payload.channels
    )

    return {
        "eventId": payload.eventId,
        "status": "queued",
        "processedAt": sent_at
    }


@app.post(
    "/events/alert.escalated",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(verify_bearer_token)],
)
def handle_alert_escalated(payload: AlertEventPayload):
    try:
        uuid.UUID(payload.eventId)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=build_problem(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                title="Unprocessable Entity",
                detail="eventId must be a valid UUID",
            ),
        )

    sent_at = datetime.now(timezone.utc).isoformat()
    inner_payload = payload.payload or payload.data
    title = f"⚠️ LEO THANG: {inner_payload.title}" if inner_payload else "Cảnh báo leo thang"
    message = inner_payload.message if inner_payload else "Sự cố leo thang mức độ nghiêm trọng"
    source = payload.source or (inner_payload.source if inner_payload else "unknown")
    target = "all"
    if payload.metadata and isinstance(payload.metadata, dict):
        target = payload.metadata.get("target", "all")

    trigger_notification_dispatch(
        event_id=payload.eventId,
        alert_id=payload.alertId,
        severity="CRITICAL",  # Escalation implies critical
        title=title,
        message=message,
        source=source,
        target=target,
        channels=payload.channels
    )

    return {
        "eventId": payload.eventId,
        "status": "queued",
        "processedAt": sent_at
    }


@app.post(
    "/events/alert.resolved",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(verify_bearer_token)],
)
def handle_alert_resolved(payload: AlertEventPayload):
    try:
        uuid.UUID(payload.eventId)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=build_problem(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                title="Unprocessable Entity",
                detail="eventId must be a valid UUID",
            ),
        )

    sent_at = datetime.now(timezone.utc).isoformat()
    inner_payload = payload.payload or payload.data
    title = f"✅ KHẮC PHỤC: {inner_payload.title}" if inner_payload else "Khắc phục sự cố"
    message = inner_payload.message if inner_payload else "Sự cố đã được khắc phục hoàn toàn"
    source = payload.source or (inner_payload.source if inner_payload else "unknown")
    target = "all"
    if payload.metadata and isinstance(payload.metadata, dict):
        target = payload.metadata.get("target", "all")

    trigger_notification_dispatch(
        event_id=payload.eventId,
        alert_id=payload.alertId,
        severity="LOW",  # resolution alerts can be low priority/log-only or notifications
        title=title,
        message=message,
        source=source,
        target=target,
        channels=payload.channels or ["telegram", "email", "app"]
    )

    return {
        "eventId": payload.eventId,
        "status": "queued",
        "processedAt": sent_at
    }


@app.get(
    "/api/v1/notifications",
    response_model=List[NotificationDelivery],
    dependencies=[Depends(verify_bearer_token)],
)
def list_notifications():
    # Query database
    select_query = """
    SELECT delivery_id, alert_id, event_id, channel, status, sent_at, delivered_at, error_message, retry_count, last_attempt_at
    FROM notifications
    ORDER BY sent_at DESC
    LIMIT 50;
    """
    rows = execute_db_query(select_query, fetch=True)
    if rows is not None:
        result = []
        for row in rows:
            result.append(
                NotificationDelivery(
                    deliveryId=row[0],
                    alertId=row[1],
                    eventId=row[2],
                    channel=row[3],
                    status=row[4],
                    sentAt=row[5],
                    deliveredAt=row[6],
                    errorMessage=row[7],
                    retryCount=row[8],
                    lastAttemptAt=row[9]
                )
            )
        return result

    # Fallback to memory
    result = []
    for item in IN_MEMORY_NOTIFICATIONS.values():
        result.append(
            NotificationDelivery(
                deliveryId=item["deliveryId"],
                alertId=item["alertId"],
                eventId=item["eventId"],
                channel=item["channel"],
                status=item["status"],
                sentAt=item["sentAt"],
                deliveredAt=item["deliveredAt"],
                errorMessage=item["errorMessage"],
                retryCount=item.get("retryCount", 0),
                lastAttemptAt=item.get("lastAttemptAt", item["sentAt"])
            )
        )
    # Sort memory items by sentAt desc
    result.sort(key=lambda x: x.sentAt, reverse=True)
    return result[:50]


@app.get(
    "/notifications/{notificationId}",
    response_model=NotificationDelivery,
    dependencies=[Depends(verify_bearer_token)],
)
def get_notification_status(notificationId: str):
    # Query database
    select_query = """
    SELECT delivery_id, alert_id, event_id, channel, status, sent_at, delivered_at, error_message, retry_count, last_attempt_at
    FROM notifications
    WHERE delivery_id = %s;
    """
    rows = execute_db_query(select_query, (notificationId,), fetch=True)
    if rows:
        row = rows[0]
        return NotificationDelivery(
            deliveryId=row[0],
            alertId=row[1],
            eventId=row[2],
            channel=row[3],
            status=row[4],
            sentAt=row[5],
            deliveredAt=row[6],
            errorMessage=row[7],
            retryCount=row[8],
            lastAttemptAt=row[9]
        )

    # Fallback to memory
    if notificationId in IN_MEMORY_NOTIFICATIONS:
        item = IN_MEMORY_NOTIFICATIONS[notificationId]
        return NotificationDelivery(
            deliveryId=item["deliveryId"],
            alertId=item["alertId"],
            eventId=item["eventId"],
            channel=item["channel"],
            status=item["status"],
            sentAt=item["sentAt"],
            deliveredAt=item["deliveredAt"],
            errorMessage=item["errorMessage"],
            retryCount=item.get("retryCount", 0),
            lastAttemptAt=item.get("lastAttemptAt", item["sentAt"])
        )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=build_problem(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Not Found",
            detail=f"Notification with ID {notificationId} not found",
            instance=f"/notifications/{notificationId}",
            problem_type="https://notification.campus.local/problems/not-found",
        ),
    )


@app.post(
    "/api/v1/alerts",
    status_code=status.HTTP_202_ACCEPTED,
)
def handle_ai_vision_alert(payload: AIVisionAlertPayload):
    print(f"[AI Vision Alert] Received: {payload}")
    
    event_id = str(uuid.uuid4())
    alert_id = f"ALT-VISION-{int(datetime.now(timezone.utc).timestamp())}"
    sent_at = datetime.now(timezone.utc).isoformat()
    
    trigger_notification_dispatch(
        event_id=event_id,
        alert_id=alert_id,
        severity=payload.severity,
        title=payload.title,
        message=payload.message,
        source=payload.source,
        target="security_team",  # AI Vision defaults to security team
        channels=None
    )
        
    return {
        "eventId": event_id,
        "status": "queued",
        "processedAt": sent_at
    }

