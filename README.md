# Lotto Shop Scanner

로또 판매점 관련 애플리케이션과 데이터 도구를 한 저장소에서 관리하는 모노레포입니다.

## 저장소 구조

```text
lottoShopScanner/
├─ apps/
│  └─ data-collector/       # 동행복권 당첨 판매점 데이터 수집기
├─ packages/                # 여러 앱이 공유할 코드(추가 예정)
├─ infrastructure/          # 배포·프록시·IaC 설정(추가 예정)
├─ .github/workflows/       # 경로 기반 CI
└─ compose.yaml             # 로컬 컨테이너 실행
```

새 프론트엔드와 백엔드는 각각 `apps/frontend`, `apps/backend` 아래에 추가합니다. 여러 앱이 함께 사용하는 타입이나 유틸리티는 `packages/`에 둡니다.

## 데이터 수집기 실행

로컬 Python으로 실행:

```powershell
python .\apps\data-collector\src\fetch_winning_shops.py 1232
```

Docker Compose로 실행:

```powershell
docker compose run --rm data-collector 1232
docker compose run --rm data-collector 1230 1232
```

결과와 로그는 호스트의 `apps/data-collector/output/`에 유지됩니다. 상세 옵션은 [데이터 수집기 문서](apps/data-collector/README.md)를 참고하세요.

## 테스트와 이미지 검증

```powershell
python -m unittest discover -s .\apps\data-collector\tests -v
docker compose build data-collector
docker compose config --quiet
```

Android 앱을 실행하지 않고 배포된 백엔드의 상태와 앱용 API 계약을 확인하려면
루트 `.env`에 외부 URL을 설정합니다.

```dotenv
API_BASE_URL=https://api.example.com
```

이후 인자 없이 실행합니다.

```bash
./scripts/test-external-api.sh
```

좌표와 검색어는 `LAT`, `LNG`, `RADIUS_M`, `SEARCH_QUERY` 환경변수로 바꿀 수 있습니다.

## 테스트 사용자 전달

실기기 테스트 사용자에게 앱을 전달하기 위한 배포용 환경값, 테스트 백엔드 준비,
Android APK/AAB와 iOS TestFlight 절차는 [테스트 사용자 전달 준비](docs/test-release.md)를
기준으로 진행합니다. 비밀값은 `.env`에만 보관하고, 새 환경에서는 `.env.example`을
복사해 실제 값을 채웁니다.

## PostgreSQL 적재 및 랭킹 테이블

PostgreSQL을 시작한 뒤 수집된 JSONL을 적재하고 랭킹을 갱신합니다.

```powershell
docker compose up -d postgres
docker compose run --build --rm db-loader
```

로컬 개발 기본 접속 정보는 데이터베이스·사용자 `lotto`, 포트 `5432`입니다. 비밀번호와
포트는 `.env`의 `POSTGRES_PASSWORD`, `POSTGRES_PORT` 등으로 변경할 수 있습니다.

주요 테이블은 다음과 같습니다.

- `draw_results`: 회차별 1·2등 당첨금과 원본 응답
- `shops`: `ltShpId` 기준 최신 판매점 정보
- `winning_events`: 당첨 게임별 판매점, 등수 및 당첨금
- `shop_statistics`: 1등·2등 횟수, 총 당첨금과 공동 순위

적재 대상 회차의 이벤트는 트랜잭션 안에서 원본과 동일하게 교체되고 판매점과 회차는
upsert되므로, 같은 명령을 다시 실행해도 당첨 이벤트가 중복되지 않습니다.

GitHub Actions는 `apps/data-collector/**`, `compose.yaml` 또는 워크플로 자체가 변경될 때 테스트와 컨테이너 빌드를 실행합니다. 이후 앱별 워크플로를 같은 방식으로 분리할 수 있습니다.
