# 테스트 사용자 전달 준비

이 문서는 Android/iOS 실기기 테스트 사용자에게 앱을 전달하기 전에 확인할 배포용 설정과 테스트 서버 준비 절차다.

## 배포용 환경값

테스트 빌드에는 다음 값을 명시적으로 전달한다.

| 이름 | 사용 위치 | 값 |
| --- | --- | --- |
| `NAVER_MAP_CLIENT_ID` | Flutter 앱 | NAVER Cloud Maps Dynamic Map Client ID |
| `API_BASE_URL` | Flutter 앱 | 외부 접속 가능한 테스트 백엔드 주소 |
| `SUPPORT_EMAIL` | Flutter 앱 | 정보 오류 제보를 받을 이메일 |
| `NAVER_GEOCODE_CLIENT_ID` | 백엔드 | NAVER 주소 지오코딩 Client ID |
| `NAVER_GEOCODE_CLIENT_SECRET` | 백엔드 | NAVER 주소 지오코딩 Client Secret |
| `DATABASE_URL` | 백엔드 | PostgreSQL/PostGIS 접속 문자열 |

앱 테스트 빌드를 만들 때 `API_BASE_URL`에는 `localhost`, `127.0.0.1`, `10.0.2.2`를 넣지 않는다. 이 주소들은 개발 머신이나 에뮬레이터 전용이므로 외부 테스트 사용자의 실기기에서는 동작하지 않는다.

## 로컬 네트워크 테스트 서버

같은 Wi-Fi에 연결된 실기기에서 빠르게 확인할 때는 Mac의 로컬 백엔드를 임시 테스트 서버로 사용할 수 있다.

1. 저장소 루트에 `.env`를 준비한다. 새 환경에서는 `.env.example`을 복사한 뒤 실제 값을 채운다.
2. 백엔드와 PostgreSQL을 실행한다.

```bash
docker compose up -d postgres backend
```

3. Mac의 LAN IP를 확인한다.

```bash
ipconfig getifaddr en0
```

4. 실기기와 Mac이 같은 네트워크에 있는지 확인한다.
5. 실기기용 Flutter 실행 또는 빌드에서 `API_BASE_URL`을 `http://<Mac LAN IP>:8000` 형태로 전달한다.

```bash
flutter run \
  --dart-define=NAVER_MAP_CLIENT_ID=<client-id> \
  --dart-define=API_BASE_URL=http://<Mac LAN IP>:8000 \
  --dart-define=SUPPORT_EMAIL=<support-email>
```

로컬 네트워크 방식은 내부 테스트용이다. 더 넓은 테스터에게 전달할 빌드는 HTTPS 테스트 서버를 사용한다.

## 외부 테스트 서버

외부 테스트 사용자에게 배포하려면 백엔드를 인터넷에서 접근 가능한 서버에 배포한다.

1. PostgreSQL/PostGIS 데이터베이스를 준비한다.
2. `DATABASE_URL`, `NAVER_GEOCODE_CLIENT_ID`, `NAVER_GEOCODE_CLIENT_SECRET`을 서버 환경변수로 설정한다.
3. 백엔드 컨테이너를 배포하고 `/docs` 또는 `/v1/places/search`로 응답을 확인한다.
4. HTTPS 도메인을 연결한다.
5. 앱 빌드의 `API_BASE_URL`을 HTTPS 주소로 설정한다.

Android 앱 밖에서 외부 접속과 주요 응답 형식을 한 번에 점검할 수 있다.
저장소 루트 `.env`의 앱 빌드용 `API_BASE_URL`을 그대로 사용한다.

```dotenv
API_BASE_URL=https://api.example.com
```

```bash
./scripts/test-external-api.sh
```

기본값은 서울시청 좌표와 `서울 중구` 검색어다. 다른 지역은 다음처럼 지정한다.

```bash
LAT=35.1796 LNG=129.0756 SEARCH_QUERY="부산 중구" \
  ./scripts/test-external-api.sh
```

## Android 전달

소수 테스터에게 빠르게 전달할 때는 APK를 만들 수 있다.

```bash
flutter build apk --release \
  --dart-define=NAVER_MAP_CLIENT_ID=<client-id> \
  --dart-define=API_BASE_URL=<https-test-backend-url> \
  --dart-define=SUPPORT_EMAIL=<support-email>
```

여러 명에게 안정적으로 배포하려면 Play Console 내부 테스트 트랙에 AAB를 올린다.

```bash
flutter build appbundle --release \
  --dart-define=NAVER_MAP_CLIENT_ID=<client-id> \
  --dart-define=API_BASE_URL=<https-test-backend-url> \
  --dart-define=SUPPORT_EMAIL=<support-email>
```

릴리즈 빌드 전에는 Android 서명 키와 `key.properties` 설정이 필요하다.

## iOS 전달

iOS는 TestFlight를 사용한다.

1. Apple Developer 계정에서 Bundle ID `com.twibap.lottoShopScanner`를 확인한다.
2. Xcode Signing & Capabilities에서 Team과 Provisioning을 설정한다.
3. App Store Connect에 앱을 등록한다.
4. Archive 또는 Flutter 빌드로 업로드용 빌드를 만든다.

```bash
flutter build ipa --release \
  --dart-define=NAVER_MAP_CLIENT_ID=<client-id> \
  --dart-define=API_BASE_URL=<https-test-backend-url> \
  --dart-define=SUPPORT_EMAIL=<support-email>
```

5. TestFlight에서 테스트 사용자 이메일을 초대한다.

## 전달 전 체크

- NAVER 지도 표시
- 현재 위치 권한 허용, 거부, 재시도
- 지역·주소 검색
- 판매점 목록과 빈 결과
- 판매점 상세
- 길찾기 버튼
- 정보 오류 제보 이메일
- 앱에 개발용 API 주소가 남아있지 않은지 확인
