#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_IMAGE="lotto-shop-scanner/backend:test"
TEST_CONTAINER=""

cleanup() {
  if [[ -n "$TEST_CONTAINER" ]]; then
    docker rm -f "$TEST_CONTAINER" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

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

cd "$ROOT_DIR"

echo "[1/7] 셸 스크립트 문법 검사"
bash -n scripts/deploy-backend-mac.sh scripts/test-backend.sh

echo "[2/7] Compose 설정 검사"
docker compose --ansi never --progress plain -f compose.yaml config --quiet
POSTGRES_PASSWORD=backend-test-password \
API_DOMAIN=backend-test.example.com \
  docker compose --ansi never --progress plain \
    -f compose.mac-server.yaml config --quiet

echo "[3/7] 백엔드 테스트 이미지 빌드"
docker build --progress plain -t "$TEST_IMAGE" apps/backend

echo "[4/7] 단위 테스트 실행"
docker run --rm \
  -v "$ROOT_DIR/apps/backend/tests:/app/tests:ro" \
  "$TEST_IMAGE" \
  python -m unittest discover -s tests -v

echo "[5/7] 이미지 보안 및 healthcheck 설정 검사"
IMAGE_USER="$(docker image inspect "$TEST_IMAGE" --format '{{.Config.User}}')"
if [[ "$IMAGE_USER" != "app" ]]; then
  echo "백엔드 이미지가 app 사용자가 아닌 '$IMAGE_USER'로 실행됩니다." >&2
  exit 1
fi
HEALTHCHECK="$(docker image inspect "$TEST_IMAGE" --format '{{json .Config.Healthcheck}}')"
if [[ -z "$HEALTHCHECK" || "$HEALTHCHECK" == "null" ]]; then
  echo "백엔드 이미지에 healthcheck가 없습니다." >&2
  exit 1
fi

echo "[6/7] Caddy 설정 검사"
docker run --rm \
  -e API_DOMAIN=backend-test.example.com \
  -v "$ROOT_DIR/infrastructure/caddy/Caddyfile:/etc/caddy/Caddyfile:ro" \
  caddy:2.10-alpine \
  caddy validate --config /etc/caddy/Caddyfile

echo "[7/7] 실제 컨테이너 liveness 검사"
TEST_CONTAINER="$(docker run -d -p 127.0.0.1::8000 "$TEST_IMAGE")"
HOST_PORT="$(docker port "$TEST_CONTAINER" 8000/tcp | sed -E 's/.*:([0-9]+)$/\1/' | head -1)"

LIVE=0
for _ in {1..30}; do
  if curl --fail --silent --show-error --max-time 2 \
    "http://127.0.0.1:$HOST_PORT/health/live" >/dev/null 2>&1; then
    LIVE=1
    break
  fi
  sleep 1
done

if [[ "$LIVE" != "1" ]]; then
  echo "임시 백엔드 컨테이너의 liveness 확인에 실패했습니다." >&2
  docker logs "$TEST_CONTAINER" >&2 || true
  exit 1
fi

echo "백엔드 전체 테스트 통과"
