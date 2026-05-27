#!/usr/bin/env bash
# Weekly topic suggestion + report generation
# Runs every Monday at 23:00 via cron
# Notification: ntfy.sh (set NTFY_TOPIC in .env or below)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$ROOT/logs/weekly_suggest_$(date +%Y%m%d_%H%M%S).log"
mkdir -p "$ROOT/logs"

# Load .env
if [ -f "$ROOT/.env" ]; then
  export $(grep -v '^#' "$ROOT/.env" | grep -v '^$' | xargs) 2>/dev/null || true
fi

NTFY_TOPIC="${NTFY_TOPIC:-seulgy-weekly}"
NOTIFY_EMAIL="${NOTIFY_EMAIL:-jieunyi1995@gmail.com}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }
notify() {
  local msg="$1"
  # ntfy.sh push notification
  if [ -n "${NTFY_TOPIC:-}" ]; then
    curl -s -d "$msg" "https://ntfy.sh/$NTFY_TOPIC" > /dev/null || true
  fi
  # Gmail via Python if SMTP_USER + SMTP_PASSWORD set
  if [ -n "${SMTP_USER:-}" ] && [ -n "${SMTP_PASSWORD:-}" ]; then
    python3 - <<PY
import smtplib, ssl
from email.message import EmailMessage
msg = EmailMessage()
msg['Subject'] = '[Seulgy] 주간 주제 선정 완료'
msg['From'] = '${SMTP_USER}'
msg['To'] = '${NOTIFY_EMAIL}'
msg.set_content("""$msg""")
with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=ssl.create_default_context()) as s:
    s.login('${SMTP_USER}', '${SMTP_PASSWORD}')
    s.send_message(msg)
PY
  fi
}

cd "$ROOT"

log "=== 주간 주제 선정 시작 ==="

# ── 1. Core 30-day pass ──────────────────────────────────────────────
log "[1/4] 스마트폰 핵심 주제 (30일)"
uv run python scripts/suggest_smartphone_topics.py --days 30 >> "$LOG" 2>&1
log "[2/4] 휴머노이드 핵심 주제 (30일)"
uv run python scripts/suggest_humanoid_topics.py --days 30 >> "$LOG" 2>&1

# ── 2. Emerging 7-day pass ───────────────────────────────────────────
log "[3/4] 스마트폰 이머징 주제 (7일)"
uv run python scripts/suggest_smartphone_emerging.py --days 7 >> "$LOG" 2>&1
log "[4/4] 휴머노이드 이머징 주제 (7일)"
uv run python scripts/suggest_humanoid_emerging.py --days 7 >> "$LOG" 2>&1

log "=== 주제 선정 완료 — 보고서 생성 시작 ==="

# ── 3. Batch report generation ───────────────────────────────────────
uv run python scripts/batch_report_gen.py --domain smartphone --delay 60 >> "$LOG" 2>&1
uv run python scripts/batch_report_gen.py --domain smartphone --include-emerging --delay 60 >> "$LOG" 2>&1
uv run python scripts/batch_report_gen.py --domain humanoid --delay 60 >> "$LOG" 2>&1
uv run python scripts/batch_report_gen.py --domain humanoid --include-emerging --delay 60 >> "$LOG" 2>&1

log "=== 전체 완료 ==="

# ── 4. 알림 전송 ─────────────────────────────────────────────────────
WEEK=$(date '+%Y-%m-%d')
SP_COUNT=$(python3 -c "import json; d=json.load(open('$ROOT/scripts/_topic_suggestions.json')); print(len(d.get('topics',[])))" 2>/dev/null || echo "?")
HM_COUNT=$(python3 -c "import json; d=json.load(open('$ROOT/scripts/_humanoid_topic_suggestions.json')); print(len(d.get('topics',[])))" 2>/dev/null || echo "?")
SP_EM=$(python3 -c "import json; d=json.load(open('$ROOT/scripts/_topic_suggestions_emerging.json')); print(len(d.get('topics',[])))" 2>/dev/null || echo "?")
HM_EM=$(python3 -c "import json; d=json.load(open('$ROOT/scripts/_humanoid_topic_suggestions_emerging.json')); print(len(d.get('topics',[])))" 2>/dev/null || echo "?")

notify "[$WEEK] 주간 주제 선정 완료 ✓
스마트폰: 핵심 ${SP_COUNT}개 + 이머징 ${SP_EM}개
휴머노이드: 핵심 ${HM_COUNT}개 + 이머징 ${HM_EM}개
로그: $LOG"

log "알림 전송 완료"
