#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env.server.mac}"
COMPOSE_FILE="$ROOT_DIR/compose.mac-server.yaml"
IMAGE="lotto-shop-scanner/backend:mac-server"
ROLLBACK_IMAGE="lotto-shop-scanner/backend:rollback"
HEALTH_RETRIES="${HEALTH_RETRIES:-60}"
LOAD_DATA=0

usage() {
  cat <<'EOF'
사용법: scripts/deploy-backend-mac.sh [--load-data]

  --load-data  백엔드 배포 후 output JSONL을 PostgreSQL에 적재합니다.

환경변수:
  ENV_FILE       환경파일 경로 (기본: .env.server.mac)
  HEALTH_RETRIES readiness 재시도 횟수, 2초 간격 (기본: 60)
EOF
}

for arg in "$@"; do
  case "$arg" in
    --load-data) LOAD_DATA=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "지원하지 않는 옵션입니다: $arg" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ ! -f "$ENV_FILE" ]]; then
  echo "환경 파일을 찾을 수 없습니다: $ENV_FILE" >&2
  echo "cp .env.server.mac.example .env.server.mac 후 실제 값을 입력하세요." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

if [[ -z "${POSTGRES_PASSWORD:-}" || "$POSTGRES_PASSWORD" == replace-with-* ]]; then
  echo "POSTGRES_PASSWORD를 $ENV_FILE 에 실제 값으로 설정하세요." >&2
  exit 1
fi
if [[ ! "$POSTGRES_PASSWORD" =~ ^[A-Za-z0-9_-]+$ ]]; then
  echo "POSTGRES_PASSWORD는 영문, 숫자, 하이픈, 밑줄만 사용할 수 있습니다." >&2
  exit 1
fi
if [[ ! "${BACKEND_PORT:-8000}" =~ ^[0-9]+$ ]]; then
  echo "BACKEND_PORT는 숫자여야 합니다." >&2
  exit 1
fi
if [[ -z "${API_DOMAIN:-}" || "$API_DOMAIN" == *"://"* || "$API_DOMAIN" == */* ]]; then
  echo "API_DOMAIN은 프로토콜과 경로가 없는 도메인이어야 합니다." >&2
  exit 1
fi
if [[ ! "$HEALTH_RETRIES" =~ ^[1-9][0-9]*$ ]]; then
  echo "HEALTH_RETRIES는 1 이상의 정수여야 합니다." >&2
  exit 1
fi

command -v docker >/dev/null 2>&1 || {
  echo "docker 명령을 찾을 수 없습니다." >&2
  exit 1
}
command -v curl >/dev/null 2>&1 || {
  echo "curl 명령을 찾을 수 없습니다." >&2
  exit 1
}
docker info >/dev/null 2>&1 || {
  echo "Docker Desktop이 실행 중이 아닙니다." >&2
  exit 1
}

COMPOSE=(
  docker compose
  --ansi never
  --progress plain
  --env-file "$ENV_FILE"
  -f "$COMPOSE_FILE"
)
cd "$ROOT_DIR"

echo "[1/6] Compose 설정 검증"
"${COMPOSE[@]}" config --quiet

HAD_PREVIOUS_IMAGE=0
if docker image inspect "$IMAGE" >/dev/null 2>&1; then
  docker tag "$IMAGE" "$ROLLBACK_IMAGE"
  HAD_PREVIOUS_IMAGE=1
fi

echo "[2/6] 백엔드 이미지 빌드"
"${COMPOSE[@]}" build backend

echo "[3/6] PostgreSQL 시작"
"${COMPOSE[@]}" up -d --wait postgres

echo "[4/6] DB 비밀번호 동기화 및 백엔드/HTTPS 프록시 시작"
printf "%s\n" \
  "SELECT format('ALTER ROLE %I PASSWORD %L', current_user, :'new_password') \\gexec" \
  | "${COMPOSE[@]}" exec -T \
      -e "NEW_POSTGRES_PASSWORD=$POSTGRES_PASSWORD" \
      postgres sh -c \
      'psql --set=ON_ERROR_STOP=1 --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --set="new_password=$NEW_POSTGRES_PASSWORD"'
"${COMPOSE[@]}" up -d backend caddy

PORT="${BACKEND_PORT:-8000}"
HEALTH_URL="http://127.0.0.1:$PORT/health/ready"
echo "[5/6] 내부 readiness 확인: $HEALTH_URL"

READY=0
for ((attempt = 1; attempt <= HEALTH_RETRIES; attempt++)); do
  if curl --fail --silent --show-error --max-time 3 "$HEALTH_URL" >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 2
done

if [[ "$READY" != "1" ]]; then
  echo "배포 후 readiness 확인에 실패했습니다." >&2
  "${COMPOSE[@]}" logs --tail=100 postgres backend >&2 || true

  if [[ "$HAD_PREVIOUS_IMAGE" == "1" ]]; then
    echo "직전 백엔드 이미지로 롤백합니다." >&2
    docker tag "$ROLLBACK_IMAGE" "$IMAGE"
    "${COMPOSE[@]}" up -d --no-build --force-recreate backend
  fi
  exit 1
fi

HTTPS_URL="https://$API_DOMAIN/health/ready"
echo "[6/6] HTTPS 인증서 및 외부 readiness 확인: $HTTPS_URL"

HTTPS_READY=0
for ((attempt = 1; attempt <= HEALTH_RETRIES; attempt++)); do
  if curl --fail --silent --show-error --max-time 5 "$HTTPS_URL" >/dev/null 2>&1; then
    HTTPS_READY=1
    break
  fi
  sleep 2
done

if [[ "$HTTPS_READY" != "1" ]]; then
  echo "HTTPS 인증서 발급 또는 외부 readiness 확인에 실패했습니다." >&2
  echo "DuckDNS의 IP, 공유기 TCP 80/443 포트포워딩, macOS 방화벽을 확인하세요." >&2
  "${COMPOSE[@]}" logs --tail=150 caddy >&2 || true
  exit 1
fi

if [[ "$LOAD_DATA" == "1" ]]; then
  echo "수집 데이터를 PostgreSQL에 적재합니다."
  "${COMPOSE[@]}" --profile tools run --rm db-loader
fi

MAC_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"
echo "배포 완료: $HEALTH_URL"
echo "외부 HTTPS 주소: https://$API_DOMAIN"
if [[ -n "$MAC_IP" ]]; then
  echo "Mac LAN IP: $MAC_IP (백엔드 8000 포트는 localhost에서만 접근 가능)"
fi
"${COMPOSE[@]}" ps
