# Lotto Shop Scanner 인수인계

이 문서는 다른 컴퓨터나 새 Codex 작업에서 개발을 이어가기 위한 기준 문서다. 대화 기록이 보이지 않더라도 이 문서와 Git 커밋 기록을 우선 기준으로 삼는다.

## 현재 상태

- 기본 브랜치: `master`
- 인수인계 작성 직전 커밋: `00bbb4f chore: lock iOS map package versions`
- 원격 저장소: `https://github.com/Twibap/lottoShopScanner.git`
- 모노레포 구성
  - `apps/data-collector`: 동행복권 공개 데이터 수집, 랭킹 생성, PostgreSQL 적재
  - `apps/backend`: FastAPI + PostGIS 기반 주변 판매점 조회 API
  - `apps/mobile`: Android/iOS Flutter 앱
  - `compose.yaml`: PostgreSQL, 적재기, 백엔드 등 로컬 컨테이너 구성

현재 구현된 범위는 다음과 같다.

1. 회차별 당첨 판매점과 추첨 결과·당첨금 수집
2. 판매점별 1등·2등 당첨 횟수, 누적 당첨금, 최근 당첨 회차와 랭킹 생성
3. PostgreSQL 스키마 및 멱등 적재
4. 판매점 좌표 품질 감사와 PostGIS 공간 인덱스
5. 반경 내 판매점 조회 API와 커서 페이지네이션
6. Flutter 탐색 화면, API 연동, 반경·랭킹 필터와 로딩·빈 결과·오류 상태
7. NAVER 지도 표시, 마커, 현재 위치 권한 및 위치 조회
8. 지역·주소·판매점 검색, 검색 중심점 이동, NAVER 주소 지오코딩 fallback
9. 판매점 상세 API와 Flutter 상세 화면, 당첨 통계·개별 이력·전국 보조 순위 표시
10. 상세 화면의 외부 지도 앱 길찾기 연결
11. 상세 화면의 정보 오류 제보 이메일 연결

## 확정된 제품 결정

- Android와 iOS를 Flutter 단일 코드베이스로 지원한다.
- 지도와 지오코딩은 NAVER Maps를 사용한다.
- 회원가입, 로그인, 광고, 결제, 복권 번호 추천은 MVP에서 제외한다.
- 위치는 주변 검색 요청에만 사용하며 서버에 위치 이력을 저장하지 않는다.
- 위치 권한을 거부해도 지역 검색으로 핵심 기능을 사용할 수 있어야 한다.
- 검색 반경 선택지는 1km, 3km, 5km, 10km다.
- API의 `radius_m` 최솟값은 `0`이다. 음수만 거부하며 임의의 최소 반경은 두지 않는다.
- 정렬 기준은 다음 다섯 가지다.
  - 가까운 순: 직선거리 오름차순
  - 1등 당첨 순: 1등 당첨 횟수 내림차순
  - 2등 당첨 순: 2등 당첨 횟수 내림차순
  - 당첨금 순: 수집 범위 내 1·2등 명목 당첨금 합계 내림차순
  - 최근 당첨 순: 가장 최근 1·2등 당첨 회차 내림차순
- 당첨금은 물가 보정 없이 명목 금액을 합산한다. 판매액이나 미래 당첨 확률을 뜻하지 않는다.
- 공동 순위는 경쟁 순위 방식이다. 예를 들어 점수가 `100, 90, 90, 80`이면 순위는 `1, 2, 2, 4`다.
- API 목록의 `result_rank`는 전국 순위가 아니라 현재 검색 반경과 정렬 조건 안의 순서다.
- 커서 페이지네이션에서 다음 페이지가 `3, 4`로 보인다는 것은 첫 페이지의 `1, 2`에 이어 전체 필터 결과의 표시 순번을 유지한다는 뜻이다. 새 페이지마다 순위를 1부터 다시 시작한다는 뜻이 아니다.
- 전국 통계 순위는 판매점 상세 화면에서만 보조 정보로 표시하고, 목록의 현재 반경 순위와 명확히 구분한다.
- 최신 회차 정기 갱신은 매주 토요일 21:00(KST)에 실행한다.
- 실패하거나 최신 회차가 아직 게시되지 않았으면 일요일 00:00, 06:00, 09:00, 12:00(KST)에 순서대로 재시도한다.
- 성공한 뒤에는 해당 회차의 남은 예약 재시도를 건너뛴다.
- 판매점·당첨 결과의 출처는 동행복권 공개 데이터, 지도·지오코딩의 출처는 NAVER Maps로 표시한다.
- 정보 오류 신고는 전용 지원 이메일로 접수하는 방향이며 실제 주소는 스토어 출시 전에 확정한다.

세부 요구사항의 기준 문서는 `docs/product-requirements.md`다.

## 좌표 검증 결과

2026-07-14 기준 10,457개 판매점을 검사했다.

- 좌표 누락·비숫자·0 좌표: 0개
- 국내 허용 범위 밖 좌표: 4개
- 동일 좌표 그룹: 69개 그룹, 143개 판매점
- 비실물 판매점 후보: 1개

범위 밖 좌표와 비실물 후보는 주변 검색에서 제외한다. 동일 좌표는 상가 내 복수 판매점이나 과거·현재 ID 병존 가능성이 있어 자동 오류로 간주하지 않는다. 자세한 내용은 `docs/coordinate-data-audit.md`에 있다.

## Mac에서 환경 복원

필수 도구는 Git, Docker Desktop, Flutter SDK, Xcode, Android Studio다. GitHub CLI(`gh`)는 편의 도구일 뿐 필수는 아니다.

```bash
git clone https://github.com/Twibap/lottoShopScanner.git
cd lottoShopScanner
git log --oneline -10
docker compose up -d postgres
docker compose run --build --rm db-loader
docker compose up --build backend
```

백엔드 문서는 `http://localhost:8000/docs`에서 확인한다. Flutter 앱 설정과 실행법은 `apps/mobile/README.md`를 따른다.

NAVER Cloud Maps에 다음 앱 식별자를 등록하고 Dynamic Map Client ID를 런타임에 전달해야 한다.

- Android package: `com.twibap.lotto_shop_scanner`
- iOS bundle identifier: `com.twibap.lottoShopScanner`

```bash
cd apps/mobile
flutter pub get
flutter run \
  --dart-define=NAVER_MAP_CLIENT_ID=your-client-id \
  --dart-define=API_BASE_URL=http://127.0.0.1:8000 \
  --dart-define=SUPPORT_EMAIL=support@example.com
```

iOS 시뮬레이터에서는 일반적으로 `127.0.0.1`로 Mac의 백엔드에 접근할 수 있다. Android 에뮬레이터의 기본 URL은 `http://10.0.2.2:8000`이다. 실제 기기는 Mac과 같은 네트워크에서 Mac의 LAN IP를 사용한다. 비밀값과 로컬 생성 데이터는 Git에 커밋하지 않는다.

## 검증 명령

저장소 루트에서 실행한다.

```bash
python -m unittest discover -s apps/data-collector/tests -v
python -m unittest discover -s apps/backend/tests -v
docker compose config --quiet
docker compose build data-collector backend

cd apps/mobile
flutter analyze
flutter test
```

## 테스트 사용자 앱 전달 준비

실기기 테스트 사용자에게 앱을 전달하기 전에 다음 작업을 순서대로 진행한다.

1. 배포용 환경값 확정
   - `NAVER_MAP_CLIENT_ID`: NAVER Cloud Maps의 Dynamic Map Client ID를 사용한다.
   - `API_BASE_URL`: 테스트 사용자가 외부 네트워크에서 접근할 수 있는 백엔드 주소로 설정한다.
   - `SUPPORT_EMAIL`: 정보 오류 제보를 받을 실제 이메일 주소로 설정한다.
   - 앱 빌드에 `localhost`, `127.0.0.1`, `10.0.2.2` 같은 개발용 주소가 남아있지 않은지 확인한다.
2. 테스트 백엔드 공개
   - 백엔드를 외부 접근 가능한 서버에 배포한다.
   - 가능하면 HTTPS를 사용한다. 모바일 네트워크, 사내 Wi-Fi, 일반 가정 Wi-Fi에서 접근을 확인한다.
   - 테스트 서버 기준으로 검색, 판매점 상세, 현재 위치, 길찾기 진입을 확인한다.
3. Android 테스트 앱 준비
   - 릴리즈 서명 키를 준비한다.
   - 테스트용 `apk` 또는 Play Console 내부 테스트용 `aab`를 생성한다.
   - 소수 테스터에게는 APK 직접 전달이 빠르다. 더 넓은 테스트에는 Google Play 내부 테스트 트랙을 사용한다.
4. iOS 테스트 앱 준비
   - Apple Developer 계정, Bundle ID, Signing, Provisioning Profile을 정리한다.
   - App Store Connect에 앱을 등록한다.
   - TestFlight 빌드를 업로드하고 테스트 사용자 이메일을 초대한다.
5. 기능 최종 점검
   - 위치 권한 요청과 거부 상태
   - 현재 위치 반영
   - NAVER 지도 표시
   - 검색 결과와 빈 결과
   - 판매점 상세 화면
   - 길찾기 버튼이 Android에서는 지도 앱, iOS에서는 Apple Maps로 이어지는 흐름
   - 정보 오류 제보 이메일 연결
6. 테스터 안내문 작성
   - 설치 방법
   - 테스트할 주요 기능
   - 알려진 제한사항
   - 오류 제보 시 필요한 정보: 기기명, OS 버전, 앱 화면 캡처, 발생 시점, 검색어 또는 판매점명

현재 기준으로 Android는 APK 직접 전달 또는 Play Console 내부 테스트를 선택하면 된다. iOS는 TestFlight 준비가 필수 단계다. 두 플랫폼 모두 테스트 사용자에게 전달하기 전에 외부 접속 가능한 백엔드 주소와 배포용 `dart-define` 값을 먼저 확정해야 한다.

## 다음 작업

우선순위는 다음과 같다.

1. NAVER 장소명 검색 연동 검토
   - 현재 검색은 NAVER 주소 지오코딩과 판매점 DB의 상호명·주소·지역 검색을 지원한다.
   - `서울시청`, `강남역`, `부산역` 같은 장소명 검색은 주소 지오코딩만으로는 결과가 없을 수 있어 별도 장소/키워드 검색 API 검토가 필요하다.
2. 실제 지원 이메일 주소 확정
3. 정기 갱신 스케줄러 및 성공 시 잔여 재시도 중단 로직 구현·운영 검증
4. 네트워크 단절, 위치 권한 거부, 빈 결과, 부분 통계 누락 상태 보완
5. Android/iOS 실기기 검증, 접근성·성능 점검, HTTPS 배포 환경 구성
6. 개인정보처리방침과 출처·비공식 서비스 고지 작성 후 스토어 출시 준비

다음 개발 단계는 NAVER 장소명 검색 연동 검토 또는 실제 지원 이메일 주소 확정이다.

## 주요 커밋

- `8fddb98`: 구현 전 제품 결정 확정
- `715d33b`: 판매점 좌표 품질 감사
- `6acbd63`: PostGIS 검색 인프라
- `7b9e1d2`: 주변 판매점 검색 API
- `9d2e66b`: Flutter 탐색 앱 기본 골격
- `127c632`: NAVER 지도와 기기 위치 연동
- `b858475`: 지역·주소 검색 API와 Flutter 검색 UI
- `b30e140`: 장소명 검색 보류 기록
- `75afa9b`: 판매점 상세 API와 상세 화면
- `4ac4c55`: 현재 위치 조회 안정화
- `6edcee2`: 지원 이메일 설정 문서화
- `b99e9ef`: 지도 비활성 안내 문구 레이아웃 보완
- `00bbb4f`: iOS 지도 패키지 버전 고정
