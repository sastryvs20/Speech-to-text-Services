#!/usr/bin/env bash
set -Eeuo pipefail

#############################################
# SCHEDULE (server local time)
#############################################
SCHEDULE_HOUR="16"     # 24h format
SCHEDULE_MINUTE="00"   # 0-59
CRON_MARK="# log-uploader (managed)"
#############################################

#############################################
# AWS CREDENTIALS (replace with real values)
#############################################
export AWS_ACCESS_KEY_ID="AKIAV3ZLP6GWRN6UN34V"
export AWS_SECRET_ACCESS_KEY="7f5oHSqPWQMxITSIm/pb1Y6Wec7yp3/LOqgox12J"
export AWS_DEFAULT_REGION="ap-south-1"
# export AWS_SESSION_TOKEN="YOUR_AWS_SESSION_TOKEN"   # if using temporary creds
#############################################

# --- CONFIG ---
LOG_DIR="/home/ubuntu/Speech-To-Text-Services/Call_Audit/daily_logs"
S3_BUCKET="asva-asset-bundle-bucket/call-audit-voxtral"
S3_PREFIX="Voxtral-logs"   # uploads go directly into this folder (no date partition)
AWS_PROFILE=""
AWS_REGION="ap-south-1"

# Upload only yesterday's log
YESTERDAY="$(date -d "yesterday" +%Y-%m-%d)"
NAME_GLOB="*${YESTERDAY}*.log"

# --- ENV/PATH & LOCK ---
export PATH="/usr/local/bin:/usr/bin:/bin"
: "${AWS_PAGER:=}"

LOGFILE="/home/ubuntu/log-uploader.log"
LOCKFILE="/home/ubuntu/log-uploader.lock"
mkdir -p "$(dirname "$LOGFILE")"

# Resolve script path (used by cron installer)
SCRIPT_PATH="$(readlink -f "$0")"

install_cron() {
  # Create/update a single managed cron entry at SCHEDULE_HOUR:SCHEDULE_MINUTE
  local tmp
  tmp="$(mktemp)"
  # Keep existing crontab except our managed line
  crontab -l 2>/dev/null | grep -v "$CRON_MARK" > "$tmp" || true
  # Add PATH line to help cron find aws; safe to repeat (cron keeps last PATH)
  {
    echo "PATH=/usr/local/bin:/usr/bin:/bin"
    echo "${SCHEDULE_MINUTE} ${SCHEDULE_HOUR} * * * /usr/bin/env bash \"$SCRIPT_PATH\" >> \"$LOGFILE\" 2>&1 ${CRON_MARK}"
  } >> "$tmp"
  crontab "$tmp"
  rm -f "$tmp"
  echo "$(date -Is) [INFO] Installed/updated cron: runs daily at ${SCHEDULE_HOUR}:${SCHEDULE_MINUTE}"
}

# Handle management flags
if [[ "${1:-}" == "--install-cron" ]]; then
  install_cron
  exit 0
fi

# --- Begin upload run (with locking and logging) ---
exec >>"$LOGFILE" 2>&1
exec 9>"$LOCKFILE"

if ! flock -n 9; then
  echo "$(date -Is) [WARN] Another instance is running. Exiting."
  exit 0
fi

# --- Check AWS CLI installed ---
if ! command -v aws >/dev/null 2>&1; then
  echo "$(date -Is) [ERROR] aws CLI not found — install it first (e.g., apt install awscli or pipx install awscli)."
  exit 1
fi

echo "$(date -Is) [INFO] Using AWS binary: $(command -v aws)"
echo "$(date -Is) [INFO] Starting S3 log upload for $YESTERDAY"

# --- Find yesterday's logs ---
shopt -s nullglob
mapfile -t FILES < <(find "$LOG_DIR" -maxdepth 1 -type f -name "$NAME_GLOB" -print | sort)

if (( ${#FILES[@]} == 0 )); then
  echo "$(date -Is) [INFO] No files matching $NAME_GLOB in $LOG_DIR"
  exit 0
fi

# --- S3 DEST PATH (NO DATE SUBFOLDER) ---
S3_BASE="s3://${S3_BUCKET}"
[[ -n "$S3_PREFIX" ]] && S3_BASE="${S3_BASE}/${S3_PREFIX}"
S3_DEST="${S3_BASE}/"   # upload into the folder root directly

# --- Upload files AS-IS; delete locally after successful upload ---
for f in "${FILES[@]}"; do
  base="$(basename "$f")"
  echo "$(date -Is) [INFO] Uploading ${f} -> ${S3_DEST}${base}"
  if aws s3 cp "$f" "${S3_DEST}${base}" --only-show-errors --region "$AWS_REGION"; then
    echo "$(date -Is) [INFO] Upload success: ${base}. Deleting local file."
    rm -f -- "$f" || echo "$(date -Is) [WARN] Failed to delete $f"
  else
    echo "$(date -Is) [ERROR] Upload failed for ${base}. Keeping local file."
  fi
done

echo "$(date -Is) [INFO] Completed run."
