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

GitHub Actions는 `apps/data-collector/**`, `compose.yaml` 또는 워크플로 자체가 변경될 때 테스트와 컨테이너 빌드를 실행합니다. 이후 앱별 워크플로를 같은 방식으로 분리할 수 있습니다.
