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

# Set NTFY_TOPIC / NOTIFY_EMAIL in .env (kept out of source — public repo)
NTFY_TOPIC="${NTFY_TOPIC:-}"
NOTIFY_EMAIL="${NOTIFY_EMAIL:-}"

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

# ── 0. Archive build ─────────────────────────────────────────────────
log "[0/4] 전체 아카이브 빌드"
uv run python scripts/build_all_archives.py >> "$LOG" 2>&1

# ── 1. Core 30-day pass ──────────────────────────────────────────────
log "[1/8] 스마트폰 핵심 주제 (14일)"
uv run python scripts/suggest_smartphone_topics.py --days 14 >> "$LOG" 2>&1
log "[2/8] 휴머노이드 핵심 주제 (30일)"
uv run python scripts/suggest_humanoid_topics.py --days 30 >> "$LOG" 2>&1
log "[3/8] 자동차 핵심 주제 (30일)"
uv run python scripts/suggest_automotive_topics.py --days 30 >> "$LOG" 2>&1
log "[4/8] 스마트글래스 핵심 주제 (30일)"
uv run python scripts/suggest_smartglass_topics.py --days 30 >> "$LOG" 2>&1

# ── 2. Emerging 7-day pass ───────────────────────────────────────────
log "[5/8] 스마트폰 이머징 주제 (7일)"
uv run python scripts/suggest_smartphone_emerging.py --days 7 >> "$LOG" 2>&1
log "[6/8] 휴머노이드 이머징 주제 (7일)"
uv run python scripts/suggest_humanoid_emerging.py --days 7 >> "$LOG" 2>&1
log "[7/8] 자동차 이머징 주제 (7일)"
uv run python scripts/suggest_automotive_emerging.py --days 7 >> "$LOG" 2>&1
log "[8/8] 스마트글래스 이머징 주제 (7일)"
uv run python scripts/suggest_smartglass_emerging.py --days 7 >> "$LOG" 2>&1

log "=== 주제 선정 완료 — 보고서 생성 시작 ==="

# ── 3. Batch report generation ───────────────────────────────────────
uv run python scripts/batch_report_gen.py --domain smartphone --delay 60 >> "$LOG" 2>&1 || log "(batch smartphone 핵심 실패/빈 토픽 — 건너뜀)"
uv run python scripts/batch_report_gen.py --domain smartphone --include-emerging --delay 60 >> "$LOG" 2>&1 || log "(batch smartphone 이머징 실패/빈 토픽 — 건너뜀)"
uv run python scripts/batch_report_gen.py --domain humanoid --delay 60 >> "$LOG" 2>&1 || log "(batch humanoid 핵심 실패/빈 토픽 — 건너뜀)"
uv run python scripts/batch_report_gen.py --domain humanoid --include-emerging --delay 60 >> "$LOG" 2>&1 || log "(batch humanoid 이머징 실패/빈 토픽 — 건너뜀)"
uv run python scripts/batch_report_gen.py --domain automotive --delay 60 >> "$LOG" 2>&1 || log "(batch automotive 핵심 실패/빈 토픽 — 건너뜀)"
uv run python scripts/batch_report_gen.py --domain automotive --include-emerging --delay 60 >> "$LOG" 2>&1 || log "(batch automotive 이머징 실패/빈 토픽 — 건너뜀)"
uv run python scripts/batch_report_gen.py --domain smartglass --delay 60 >> "$LOG" 2>&1 || log "(batch smartglass 핵심 실패/빈 토픽 — 건너뜀)"
uv run python scripts/batch_report_gen.py --domain smartglass --include-emerging --delay 60 >> "$LOG" 2>&1 || log "(batch smartglass 이머징 실패/빈 토픽 — 건너뜀)"

# ── 3.5 EN 요약 백필 (신규 보고서 제목·핵심요약 자동 번역, 멱등 — 실패해도 보고서엔 영향 없음) ──
log "[+] EN 요약 백필"
uv run python scripts/backfill_en_summary.py >> "$LOG" 2>&1 || log "(EN 요약 백필 일부 실패 — 보고서 생성에는 영향 없음)"

log "=== 전체 완료 ==="

# ── 4. 알림 전송 ─────────────────────────────────────────────────────
WEEK=$(date '+%Y-%m-%d')
SP_COUNT=$(python3 -c "import json; d=json.load(open('$ROOT/scripts/_topic_suggestions.json')); print(len(d.get('topics',[])))" 2>/dev/null || echo "?")
HM_COUNT=$(python3 -c "import json; d=json.load(open('$ROOT/scripts/_humanoid_topic_suggestions.json')); print(len(d.get('topics',[])))" 2>/dev/null || echo "?")
AU_COUNT=$(python3 -c "import json; d=json.load(open('$ROOT/scripts/_automotive_topic_suggestions.json')); print(len(d.get('topics',[])))" 2>/dev/null || echo "?")
SG_COUNT=$(python3 -c "import json; d=json.load(open('$ROOT/scripts/_smartglass_topic_suggestions.json')); print(len(d.get('topics',[])))" 2>/dev/null || echo "?")
SP_EM=$(python3 -c "import json; d=json.load(open('$ROOT/scripts/_topic_suggestions_emerging.json')); print(len(d.get('topics',[])))" 2>/dev/null || echo "?")
HM_EM=$(python3 -c "import json; d=json.load(open('$ROOT/scripts/_humanoid_topic_suggestions_emerging.json')); print(len(d.get('topics',[])))" 2>/dev/null || echo "?")
AU_EM=$(python3 -c "import json; d=json.load(open('$ROOT/scripts/_automotive_topic_suggestions_emerging.json')); print(len(d.get('topics',[])))" 2>/dev/null || echo "?")
SG_EM=$(python3 -c "import json; d=json.load(open('$ROOT/scripts/_smartglass_topic_suggestions_emerging.json')); print(len(d.get('topics',[])))" 2>/dev/null || echo "?")

notify "[$WEEK] 주간 주제 선정 완료 ✓
스마트폰: 핵심 ${SP_COUNT}개 + 이머징 ${SP_EM}개
휴머노이드: 핵심 ${HM_COUNT}개 + 이머징 ${HM_EM}개
자동차: 핵심 ${AU_COUNT}개 + 이머징 ${AU_EM}개
스마트글래스: 핵심 ${SG_COUNT}개 + 이머징 ${SG_EM}개
로그: $LOG"

log "알림 전송 완료"
