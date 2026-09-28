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
  local subject="${2:-[Seulgy] 주간 주제 선정 완료}"
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
msg['Subject'] = '''${subject}'''
msg['From'] = '${SMTP_USER}'
msg['To'] = '${NOTIFY_EMAIL}'
msg.set_content("""$msg""")
with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=ssl.create_default_context()) as s:
    s.login('${SMTP_USER}', '${SMTP_PASSWORD}')
    s.send_message(msg)
PY
  fi
}

# 예기치 않은 중단(가드되지 않은 명령 실패)도 반드시 알린다 — 2026-07-20 GLM 502
# 장애가 월요일 밤부터 금요일까지 무음으로 방치된 원인.
on_error() {
  local rc=$?
  log "[!] 예기치 않은 중단 (exit $rc)"
  notify "[Seulgy] 주간 파이프라인 비정상 종료 (exit $rc)
로그: $LOG" "[Seulgy] 주간 파이프라인 실패" || true
}
trap on_error ERR

# 실패해도 나머지 단계를 계속 진행하는 단계 실행 helper.
# set -e 하에서 $? 를 신뢰할 수 없으므로 set +e 로 감싸 rc 를 명시적으로 캡처한다.
FAILED_STEPS=()
run_step() {
  local label="$1"; shift
  log "$label"
  set +e
  "$@" >> "$LOG" 2>&1
  local rc=$?
  set -e
  if [ $rc -ne 0 ]; then
    log "  [!] 실패 (exit $rc) — 건너뜀: $label"
    FAILED_STEPS+=("$label")
  fi
  return 0
}

cd "$ROOT"

log "=== 주간 주제 선정 시작 ==="

network_started=$SECONDS
network_ok=0
while [ "$((SECONDS - network_started))" -lt 1800 ]; do
  attempt_started=$SECONDS
  if curl -sS -o /dev/null -m 10 https://open.bigmodel.cn 2>/dev/null; then network_ok=1; break; fi
  log "[!] 네트워크 확인 실패 (${SECONDS}s 경과)"
  remaining=$((60 - (SECONDS - attempt_started)))
  if [ "$remaining" -gt 0 ]; then sleep "$remaining"; fi
done
if [ "$network_ok" -eq 0 ]; then
  log "[!] 네트워크 불가 30분 — 이번 주 작업 건너뜀"
  trap - ERR
  notify "[Seulgy] 네트워크 불가 30분 — 이번 주 작업 건너뜀
로그: $LOG" || true
  exit 1
fi

# ── 0. Archive build ─────────────────────────────────────────────────
run_step "[0/4] 전체 아카이브 빌드" uv run python scripts/build_all_archives.py

# ── 1. Core 30-day pass ──────────────────────────────────────────────
run_step "[1/8] 스마트폰 핵심 주제 (14일)" uv run python scripts/suggest_smartphone_topics.py --days 14
run_step "[2/8] 휴머노이드 핵심 주제 (30일)" uv run python scripts/suggest_humanoid_topics.py --days 30
run_step "[3/8] 자동차 핵심 주제 (30일)" uv run python scripts/suggest_automotive_topics.py --days 30
run_step "[4/8] 스마트글래스 핵심 주제 (30일)" uv run python scripts/suggest_smartglass_topics.py --days 30

# ── 2. Emerging 7-day pass ───────────────────────────────────────────
run_step "[5/8] 스마트폰 이머징 주제 (7일)" uv run python scripts/suggest_smartphone_emerging.py --days 7
run_step "[6/8] 휴머노이드 이머징 주제 (7일)" uv run python scripts/suggest_humanoid_emerging.py --days 7
run_step "[7/8] 자동차 이머징 주제 (7일)" uv run python scripts/suggest_automotive_emerging.py --days 7
run_step "[8/8] 스마트글래스 이머징 주제 (7일)" uv run python scripts/suggest_smartglass_emerging.py --days 7

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

SUMMARY="스마트폰: 핵심 ${SP_COUNT}개 + 이머징 ${SP_EM}개
휴머노이드: 핵심 ${HM_COUNT}개 + 이머징 ${HM_EM}개
자동차: 핵심 ${AU_COUNT}개 + 이머징 ${AU_EM}개
스마트글래스: 핵심 ${SG_COUNT}개 + 이머징 ${SG_EM}개
로그: $LOG"

# ${#FAILED_STEPS[@]} 는 빈 배열에도 안전 — bash 3.2 + set -u 에서
# ${FAILED_STEPS[@]} 직접 전개는 unbound variable 오류이므로 개수로 먼저 게이트한다.
if [ ${#FAILED_STEPS[@]} -eq 0 ]; then
  notify "[$WEEK] 주간 주제 선정 완료 ✓
$SUMMARY"
else
  FAILED_LIST=""
  for step in "${FAILED_STEPS[@]}"; do
    FAILED_LIST="$FAILED_LIST
  · $step"
  done
  notify "[$WEEK] 주간 주제 선정 부분 완료 ⚠ (실패 ${#FAILED_STEPS[@]}건)
$SUMMARY

실패 단계:$FAILED_LIST" "[Seulgy] 주간 주제 선정 부분 완료 (실패 ${#FAILED_STEPS[@]}건)"
fi

log "알림 전송 완료"
