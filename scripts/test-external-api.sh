#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"

if [[ -z "${API_BASE_URL:-}" && -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

API_BASE_URL="${1:-${API_BASE_URL:-}}"
LAT="${LAT:-37.5665}"
LNG="${LNG:-126.9780}"
RADIUS_M="${RADIUS_M:-3000}"
SEARCH_QUERY="${SEARCH_QUERY:-서울 중구}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-10}"

if [[ -z "$API_BASE_URL" ]]; then
  echo "API_BASE_URL이 필요합니다. $ENV_FILE 에 다음 값을 설정하세요:" >&2
  echo "API_BASE_URL=https://api.example.com" >&2
  exit 2
fi

API_BASE_URL="${API_BASE_URL%/}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

PASS_COUNT=0

request() {
  local name="$1"
  local path="$2"
  local expected_status="$3"
  local output_file="$TMP_DIR/response.json"
  local status

  status="$(curl --silent --show-error --location \
    --connect-timeout "$TIMEOUT_SECONDS" \
    --max-time "$TIMEOUT_SECONDS" \
    --output "$output_file" \
    --write-out '%{http_code}' \
    "$API_BASE_URL$path")"

  if [[ "$status" != "$expected_status" ]]; then
    echo "[실패] $name: HTTP $status (예상: $expected_status)" >&2
    sed -n '1,20p' "$output_file" >&2
    exit 1
  fi

  RESPONSE_FILE="$output_file"
  PASS_COUNT=$((PASS_COUNT + 1))
  echo "[통과] $name (HTTP $status)"
}

assert_json() {
  local expression="$1"
  local description="$2"

  python3 - "$RESPONSE_FILE" "$expression" "$description" <<'PY'
import json
import sys

path, expression, description = sys.argv[1:]
try:
    with open(path, encoding="utf-8") as response_file:
        payload = json.load(response_file)
    allowed = {"data": payload, "isinstance": isinstance, "list": list, "dict": dict, "str": str}
    if not eval(expression, {"__builtins__": {}}, allowed):
        raise AssertionError(description)
except Exception as exc:
    print(f"[실패] JSON 검증: {description}: {exc}", file=sys.stderr)
    raise SystemExit(1)
PY
}

urlencode() {
  python3 - "$1" <<'PY'
import sys
import urllib.parse
print(urllib.parse.quote(sys.argv[1], safe=""))
PY
}

echo "외부 API 스모크 테스트: $API_BASE_URL"

request "프로세스 상태" "/health/live" "200"
assert_json 'data.get("status") == "ok"' 'status가 ok여야 합니다'

request "DB 준비 상태" "/health/ready" "200"
assert_json 'data.get("status") == "ok"' 'DB 연결 상태가 ok여야 합니다'

request "주변 판매점" "/v1/shops/nearby?lat=$LAT&lng=$LNG&radius_m=$RADIUS_M&sort=distance&limit=10" "200"
assert_json 'isinstance(data.get("items"), list) and isinstance(data.get("search"), dict)' 'items 배열과 search 객체가 필요합니다'
NEARBY_FILE="$TMP_DIR/nearby.json"
cp "$RESPONSE_FILE" "$NEARBY_FILE"

ENCODED_QUERY="$(urlencode "$SEARCH_QUERY")"
request "장소 검색" "/v1/places/search?q=$ENCODED_QUERY&limit=10" "200"
assert_json 'isinstance(data.get("items"), list) and data.get("query")' 'items 배열과 query가 필요합니다'

SHOP_ID="$(python3 - "$NEARBY_FILE" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as response_file:
    items = json.load(response_file).get("items", [])
print(items[0].get("shop_id", "") if items else "")
PY
)"

if [[ -n "$SHOP_ID" ]]; then
  ENCODED_SHOP_ID="$(urlencode "$SHOP_ID")"
  request "판매점 상세" "/v1/shops/$ENCODED_SHOP_ID?lat=$LAT&lng=$LNG&radius_m=$RADIUS_M&sort=distance" "200"
  assert_json 'str(data.get("shop_id", "")) != "" and data.get("name")' '상세 응답에 shop_id와 name이 필요합니다'
else
  echo "[건너뜀] 판매점 상세: 주변 검색 결과가 없습니다"
fi

request "잘못된 위도 거부" "/v1/shops/nearby?lat=0&lng=$LNG" "422"

echo "완료: ${PASS_COUNT}개 요청 통과"
