#!/usr/bin/env bash
# Monitors a vLLM FastAPI server and restarts it if unhealthy.
# Checks every 30 seconds, activates your env, cd's into a work dir, and runs your start command with nohup.

set -euo pipefail

#####################################
# >>> EDIT THESE TO MATCH YOUR SETUP
#####################################

# Use python venv (NOT conda)
USE_CONDA=false
VENV_DIR="/home/ubuntu/voxtral_env"

# Where to run vLLM from (logs will be written here)
WORK_DIR="/home/ubuntu"

# vLLM start command (keep nohup & logging; PID will be captured)
START_CMD='nohup vllm serve mistralai/Voxtral-Small-24B-2507 \
  --tokenizer_mode mistral \
  --config_format mistral \
  --load_format mistral \
  --kv_cache_dtype auto \
  --tensor_parallel_size 4 \
  --dtype bfloat16 \
  --gpu_memory_utilization 0.90 \
  >> vllm.log 2>&1 & echo $! > vllm.pid'

# Health check settings
PORT=8000
HEALTH_URL="http://192.168.0.154:${PORT}/v1/models"  # vLLM exposes OpenAI-compatible /v1/models
CHECK_INTERVAL=240                                     # seconds

#####################################
# <<< END USER SETTINGS
#####################################

LOCK_FILE="/tmp/vllm_monitor.lock"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

activate_env() {
  if [[ "${USE_CONDA}" == "true" ]]; then
    # shellcheck disable=SC1090
    source "${CONDA_SH}"
    conda activate "${CONDA_ENV}"
  else
    # shellcheck disable=SC1091
    source "${VENV_DIR}/bin/activate"
  fi
}

is_healthy() {
  # Returns 0 if healthy, 1 otherwise
  curl -sS -m 5 -f "${HEALTH_URL}" >/dev/null 2>&1
}

start_server() {
  log "Starting vLLM server..."
  activate_env
  cd "${WORK_DIR}"
  bash -lc "${START_CMD}"
  sleep 5
  if is_healthy; then
    log "vLLM started and is healthy."
  else
    log "Warning: vLLM started but health check still failing."
  fi
}

stop_server_if_stale() {
  local pid_file="${WORK_DIR}/vllm.pid"
  if [[ -f "${pid_file}" ]]; then
    local pid
    pid="$(cat "${pid_file}" || true)"
    if [[ -n "${pid}" ]] && ps -p "${pid}" >/dev/null 2>&1; then
      log "Stopping stale vLLM process (PID ${pid})..."
      kill "${pid}" || true
      sleep 3
      if ps -p "${pid}" >/dev/null 2>&1; then
        log "Process still running; sending SIGKILL..."
        kill -9 "${pid}" || true
      fi
    fi
    rm -f "${pid_file}" || true
  fi

  # Extra safety: kill any lingering 'vllm serve' processes on the same model/port
  if pgrep -f "vllm serve .*Voxtral-Small-24B-2507" >/dev/null 2>&1; then
    log "Killing lingering vLLM processes by pattern..."
    pkill -f "vllm serve .*Voxtral-Small-24B-2507" || true
    sleep 2
  fi
}

main_loop() {
  log "vLLM monitor started. Health: ${HEALTH_URL}; Interval: ${CHECK_INTERVAL}s"
  while true; do
    if is_healthy; then
      sleep "${CHECK_INTERVAL}"
      continue
    fi
    log "Health check FAILED."
    stop_server_if_stale
    start_server
    sleep "${CHECK_INTERVAL}"
  done
}

# Ensure only one monitor instance runs
exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  log "Another monitor instance is already running (lock: ${LOCK_FILE}). Exiting."
  exit 0
fi

trap 'log "Monitor exiting."; exit 0' INT TERM
main_loop
