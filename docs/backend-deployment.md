# 백엔드 배포 가이드

백엔드는 `apps/backend/Dockerfile`로 빌드되는 stateless 컨테이너다. PostgreSQL은
PostGIS 확장을 지원해야 하며, 운영 데이터베이스와 HTTPS 종료 지점은 배포 플랫폼에서
별도로 제공하는 구성을 권장한다.

## 필수 환경변수

| 이름 | 필수 | 설명 |
| --- | --- | --- |
| `DATABASE_URL` | 예 | `postgresql://USER:PASSWORD@HOST:5432/DB?sslmode=require` 형식 |
| `PORT` | 아니요 | HTTP 포트. 기본값 `8000` |
| `WEB_CONCURRENCY` | 아니요 | Uvicorn worker 수. 기본값 `1` |
| `FORWARDED_ALLOW_IPS` | 아니요 | 신뢰할 reverse proxy IP. 기본값 `127.0.0.1` |
| `GRACEFUL_SHUTDOWN_TIMEOUT` | 아니요 | 정상 종료 대기 시간(초). 기본값 `30` |
| `NAVER_GEOCODE_CLIENT_ID` | 아니요 | NAVER 주소 검색 Client ID |
| `NAVER_GEOCODE_CLIENT_SECRET` | 아니요 | NAVER 주소 검색 Client Secret |

비밀값은 이미지나 저장소에 넣지 않고 플랫폼의 secret manager로 주입한다. 관리형 DB가
TLS를 요구하면 `DATABASE_URL`에 `sslmode=require`를 명시한다.

## 빌드와 사전 검증

저장소 루트에서 다음을 실행한다.

```bash
python -m unittest discover -s apps/backend/tests -v
docker build -t lotto-shop-scanner-backend:VERSION apps/backend
docker compose config --quiet
```

DB 스키마는 앱 시작과 분리해서 한 번 적용한다. `init.sql`은 반복 실행할 수 있게 작성되어
있지만, 실행 전 DB 스냅샷 또는 관리형 DB 백업을 확보한다.

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f infrastructure/postgres/init.sql
```

초기 데이터가 필요한 환경에서는 데이터 수집 결과를 준비한 뒤 `db-loader`와 같은 적재
작업을 앱 배포와 별도의 일회성 작업으로 실행한다.

## 플랫폼 설정

- 컨테이너 포트는 `PORT`와 동일하게 설정한다.
- liveness probe는 `GET /health/live`, readiness probe는 `GET /health/ready`를 사용한다.
- readiness는 DB에 `SELECT 1`을 실행하며, DB 연결 실패 시 HTTP 503을 반환한다.
- 외부 트래픽은 HTTPS로만 받고 HTTP는 HTTPS로 전환한다.
- 최소 두 인스턴스를 쓰는 경우 rolling update에서 readiness 통과 후 트래픽을 연결한다.
- 종료 유예 시간은 `GRACEFUL_SHUTDOWN_TIMEOUT` 이상으로 둔다.
- `FORWARDED_ALLOW_IPS`는 실제 reverse proxy 대역만 허용한다. 플랫폼이 네트워크를
  격리해 proxy 외 접근을 막는 경우에만 `*`를 사용한다.

## 개발 Mac을 임시 서버로 사용

`compose.mac-server.yaml`은 백엔드, PostGIS, Caddy HTTPS 프록시를 함께 실행한다.
PostgreSQL 5432는 Docker 네트워크 안에만 있고 Caddy가 공개 80/443 요청을 백엔드로
전달한다. 백엔드 8000 포트는 Mac의 localhost에만 열어 로컬 진단에 사용한다.

### 1. 공유기와 Mac 준비

1. 공유기에서 Mac의 DHCP 임대 주소를 고정한다.
2. macOS 방화벽에서 Docker의 수신 연결을 허용한다.
3. ipTIME 포트포워딩에서 외부 TCP 80 → Mac TCP 80, 외부 TCP/UDP 443 → Mac
   TCP/UDP 443을 설정한다. 공유기 원격 관리 포트가 80/443이면 다른 포트로 바꾼다.
4. DDNS의 공인 IP가 공유기 WAN IP와 같은지 확인한다.

### 2. 비밀값 설정

```bash
cp .env.server.mac.example .env.server.mac
```

`.env.server.mac`의 `POSTGRES_PASSWORD`를 실제 값으로 바꾼다. PostgreSQL 비밀번호는
DATABASE URL에 안전하게 포함되도록 영문, 숫자, `-`, `_`로 된 긴 값을 사용한다. 이
파일은 Git에서 제외된다.

공개 도메인도 설정한다.

```dotenv
API_DOMAIN=api.example.com
```

`*.iptime.org` DDNS는 상위 도메인의 CAA 정책이 공개 TLS 인증서 발급을 차단하므로
Caddy 자동 HTTPS에 사용할 수 없다. 테스트에는 소유한 도메인을 권장한다. 임시로
`<이름>.<공인-IP의 점을 하이픈으로 변경>.sslip.io` 형식을 사용할 수 있지만 공인 IP가
바뀌면 `API_DOMAIN`과 앱의 `API_BASE_URL`을 함께 갱신해야 한다.

### 3. 시작 및 확인

저장소 루트에서 배포 스크립트를 실행한다. 스크립트는 환경값과 Compose 설정을 검증하고,
이미지를 빌드한 뒤 내부 readiness와 외부 HTTPS 인증서 검증이 통과할 때까지 기다린다.
실패하면 로그를 출력하고 직전
백엔드 이미지가 있을 경우 자동으로 롤백한다. Compose 출력은 터미널 애니메이션 없이
한 줄씩 기록되는 plain 형식이다. 기존 PostgreSQL 볼륨의 비밀번호와 환경파일 값이
다르면 DB 역할 비밀번호를 현재 `POSTGRES_PASSWORD`로 동기화한 뒤 백엔드를 시작한다.

```bash
./scripts/deploy-backend-mac.sh
```

수집 결과도 함께 적재하려면 다음 옵션을 사용한다.

```bash
./scripts/deploy-backend-mac.sh --load-data
```

수동으로 실행할 때는 아래 명령을 사용한다.

```bash
docker compose --env-file .env.server.mac -f compose.mac-server.yaml config --quiet
docker compose --env-file .env.server.mac -f compose.mac-server.yaml up -d --build
docker compose --env-file .env.server.mac -f compose.mac-server.yaml ps
docker compose --env-file .env.server.mac -f compose.mac-server.yaml logs -f backend caddy
```

Mac의 LAN IP를 확인하고 같은 Wi-Fi의 테스트 기기에서 상태를 확인한다.

```bash
ipconfig getifaddr en0
curl --fail http://MAC_LAN_IP:8000/health/live
curl --fail http://MAC_LAN_IP:8000/health/ready
```

수집된 JSONL을 처음 적재하거나 갱신할 때는 별도 일회성 작업을 실행한다.

```bash
docker compose --env-file .env.server.mac -f compose.mac-server.yaml \
  --profile tools run --rm db-loader
```

### 4. Mac 상시 실행 설정

- Docker Desktop의 `Start Docker Desktop when you sign in`을 켠다.
- 시스템 설정에서 전원 연결 중 자동 잠자기를 해제한다. 화면 끄기는 허용해도 된다.
- Docker Desktop이 시작되면 `restart: unless-stopped` 컨테이너가 다시 실행된다.
- Mac 재부팅 후 `docker compose ... ps`와 외부 HTTPS 상태를 다시 확인한다.
- Android 디버그 실행의 `API_BASE_URL`을 `http://MAC_LAN_IP:8000`으로 설정한다.
  Android 릴리스 빌드와 iOS는 평문 HTTP를 차단하므로 현재 구성은 Flutter 개발 실행용이다.

외부에서는 8000을 직접 포트포워딩하지 않고 Caddy의 HTTPS 443만 사용한다. 인증서 최초
발급과 HTTP→HTTPS 전환을 위해 80 포트도 Caddy에 전달한다.

중지할 때는 아래 명령을 사용한다. `down`만으로 DB와 인증서 볼륨은 삭제되지 않는다.

```bash
docker compose --env-file .env.server.mac -f compose.mac-server.yaml down
```

## 배포 확인

```bash
curl --fail https://API_HOST/health/live
curl --fail https://API_HOST/health/ready
curl --fail "https://API_HOST/v1/shops/nearby?lat=37.5665&lng=126.9780&radius_m=3000&limit=1"
```

배포 직후 5xx 비율, 응답 시간, 컨테이너 재시작 횟수, DB 연결 수를 확인한다. 모바일 앱의
`API_BASE_URL`은 위 HTTPS 주소로 빌드해야 한다.

## 롤백

애플리케이션 이상 시 플랫폼에서 직전 이미지 태그로 되돌린다. 스키마 변경이 포함된
배포는 구버전과 호환되는 확장 방식으로 먼저 배포하고, 파괴적 변경은 별도 후속 배포로
분리한다. 데이터 복원이 필요할 때는 새 쓰기를 차단한 뒤 사전에 확보한 DB 백업을 사용한다.
