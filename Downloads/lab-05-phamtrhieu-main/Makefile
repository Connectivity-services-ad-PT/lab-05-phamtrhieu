.PHONY: compose-up compose-down logs run-local test-health

compose-up:
	docker compose up -d --build

compose-down:
	docker compose down

logs:
	docker compose logs -f notification

run-local:
	uvicorn notification_app.main:app --app-dir src --host 0.0.0.0 --port 8100 --reload

test-health:
	curl -s http://localhost:8100/health | python3 -m json.tool

test-alert:
	curl -s -X POST http://localhost:8100/test-alert \
	  -H "Content-Type: application/json" \
	  -d '{"event_type":"core.alert.created","source_service":"team-core","alert_id":"ALT-TEST-001","alert_type":"fire","severity":"critical","message":"Test phat hien khoi tai Lab A101","origin_event_id":"sensor-001","target":"security_team","timestamp":"2026-06-07T14:30:17+07:00"}' \
	  | python3 -m json.tool
