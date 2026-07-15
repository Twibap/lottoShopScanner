#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "환경 파일을 찾을 수 없습니다: $ENV_FILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

if [[ -z "${NAVER_MAP_CLIENT_ID:-}" ]]; then
  echo "NAVER_MAP_CLIENT_ID가 $ENV_FILE 에 필요합니다." >&2
  exit 1
fi

cd "$ROOT_DIR"

if [[ "${START_BACKEND:-1}" == "1" ]]; then
  docker compose up -d postgres backend
fi

if [[ -z "${DEVICE_ID:-}" ]]; then
  DEVICE_ID="$({ flutter devices || true; } | awk -F '•' '/android-(arm|x64)/ {gsub(/^[ \t]+|[ \t]+$/, "", $2); print $2; exit}')"
fi

if [[ -z "${DEVICE_ID:-}" ]]; then
  echo "연결된 Android 실기기를 찾지 못했습니다." >&2
  echo "flutter devices로 확인하거나 DEVICE_ID를 지정해 주세요." >&2
  exit 1
fi

if [[ -z "${API_BASE_URL:-}" ]]; then
  if command -v adb >/dev/null 2>&1; then
    adb -s "$DEVICE_ID" reverse tcp:8000 tcp:8000
    API_BASE_URL="http://127.0.0.1:8000"
  else
    MAC_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"
    if [[ -z "$MAC_IP" ]]; then
      echo "Mac의 로컬 IP를 찾지 못했습니다. .env에 API_BASE_URL을 지정해 주세요." >&2
      exit 1
    fi
    API_BASE_URL="http://$MAC_IP:8000"
  fi
fi

FLUTTER_ARGS=(
  run
  -d "$DEVICE_ID"
  "--dart-define=NAVER_MAP_CLIENT_ID=$NAVER_MAP_CLIENT_ID"
  "--dart-define=API_BASE_URL=$API_BASE_URL"
)

if [[ -n "${SUPPORT_EMAIL:-}" ]]; then
  FLUTTER_ARGS+=("--dart-define=SUPPORT_EMAIL=$SUPPORT_EMAIL")
fi

echo "기기: $DEVICE_ID"
echo "API: $API_BASE_URL"
cd "$ROOT_DIR/apps/mobile"
exec flutter "${FLUTTER_ARGS[@]}"
