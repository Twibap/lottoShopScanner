#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MOBILE_DIR="$ROOT_DIR/apps/mobile"
DEVICE_ID=""
SKIP_BUILD=0

usage() {
  cat <<'EOF'
사용법: scripts/test-frontend.sh [--skip-build] [--device DEVICE_ID]

기본 검사:
  - Dart 포맷
  - Flutter 정적 분석
  - 단위·위젯 테스트
  - Android 디버그 APK 빌드

옵션:
  --skip-build       Android APK 빌드를 생략합니다.
  --device DEVICE_ID 지정한 기기에서 지도 통합 테스트도 실행합니다.

통합 테스트 환경변수:
  NAVER_MAP_CLIENT_ID  NAVER Dynamic Map Client ID (필수)
  API_BASE_URL         테스트 백엔드 HTTPS 주소
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-build)
      SKIP_BUILD=1
      shift
      ;;
    --device)
      if [[ $# -lt 2 || -z "$2" ]]; then
        echo "--device 뒤에 기기 ID가 필요합니다." >&2
        exit 2
      fi
      DEVICE_ID="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "지원하지 않는 옵션입니다: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

command -v flutter >/dev/null 2>&1 || {
  echo "flutter 명령을 찾을 수 없습니다." >&2
  exit 1
}
command -v dart >/dev/null 2>&1 || {
  echo "dart 명령을 찾을 수 없습니다." >&2
  exit 1
}

cd "$MOBILE_DIR"

echo "[1/5] Flutter 의존성 확인"
flutter pub get

echo "[2/5] Dart 포맷 검사"
dart format --output=none --set-exit-if-changed lib test integration_test

echo "[3/5] Flutter 정적 분석"
flutter analyze

echo "[4/5] 단위 및 위젯 테스트"
flutter test test

if [[ "$SKIP_BUILD" == "1" ]]; then
  echo "[5/5] Android 디버그 APK 빌드 생략"
else
  echo "[5/5] Android 디버그 APK 빌드"
  flutter build apk --debug \
    --dart-define="NAVER_MAP_CLIENT_ID=${NAVER_MAP_CLIENT_ID:-frontend-build-check}" \
    --dart-define="API_BASE_URL=${API_BASE_URL:-https://twibap.duckdns.org}"
fi

if [[ -n "$DEVICE_ID" ]]; then
  if [[ -z "${NAVER_MAP_CLIENT_ID:-}" ]]; then
    echo "지도 통합 테스트에는 NAVER_MAP_CLIENT_ID가 필요합니다." >&2
    exit 1
  fi

  echo "[통합] 기기 지도 상호작용 테스트: $DEVICE_ID"
  flutter test integration_test/map_interaction_test.dart \
    -d "$DEVICE_ID" \
    --dart-define="NAVER_MAP_CLIENT_ID=$NAVER_MAP_CLIENT_ID" \
    --dart-define="API_BASE_URL=${API_BASE_URL:-https://twibap.duckdns.org}"
fi

echo "프론트엔드 전체 테스트 통과"
