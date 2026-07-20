# Lotto Shop Scanner Mobile

Flutter app for Android and iOS. The first app shell includes nearby-shop API
integration, radius and ranking filters, and loading, empty, and error states.
The map area is a placeholder until NAVER Maps credentials and the Flutter SDK
wrapper are configured.

## Run

Start the backend from the repository root:

```powershell
docker compose up -d postgres backend
```

Register Android package `com.twibap.lotto_shop_scanner` and iOS bundle identifier
`com.twibap.lottoShopScanner` in NAVER Cloud Maps, then pass the Dynamic Map Client
ID at runtime.
Run on an Android emulator. The default API URL is `http://10.0.2.2:8000`:

```powershell
C:\Users\Twibap\flutter\bin\flutter.bat run `
  --dart-define=NAVER_MAP_CLIENT_ID=your-client-id
```

Override the API URL for a physical device or iOS simulator:

```powershell
C:\Users\Twibap\flutter\bin\flutter.bat run `
  --dart-define=NAVER_MAP_CLIENT_ID=your-client-id `
  --dart-define=API_BASE_URL=http://192.168.0.10:8000
```

`scripts/run-mobile-device.sh` reads `API_BASE_URL` from the root `.env`. When
that value is set, it uses the external backend without starting a local Compose
stack. Set `START_BACKEND=1` explicitly only when a separate local development
backend is needed; that stack uses the `lotto-shop-scanner-dev` Compose project
name so it cannot replace the Mac server containers.

Connect the in-app incorrect-info report button by passing a support mailbox:

```powershell
C:\Users\Twibap\flutter\bin\flutter.bat run `
  --dart-define=NAVER_MAP_CLIENT_ID=your-client-id `
  --dart-define=API_BASE_URL=http://192.168.0.10:8000 `
  --dart-define=SUPPORT_EMAIL=support@example.com
```

For tester delivery builds, use the checklist in `docs/test-release.md`. Do not
ship builds that point `API_BASE_URL` to `localhost`, `127.0.0.1`, or
`10.0.2.2`; those addresses are for local development only.

Local cleartext HTTP is enabled only in the Android debug manifest. Production
builds must use HTTPS.

The app requests foreground location permission only after the user taps the
current-location button. It does not request or declare background location.

## Compatibility note

`flutter_naver_map` 1.4.4 builds successfully with Flutter 3.44.6, but currently
emits Flutter's warning that the plugin still applies the Kotlin Gradle Plugin
instead of using Built-in Kotlin. Track plugin releases before upgrading Flutter;
a future Flutter version may turn this warning into a build failure.

## Verify

저장소 루트에서 포맷, 정적 분석, 단위·위젯 테스트와 Android 디버그 빌드를 한 번에
검사합니다.

```bash
./scripts/test-frontend.sh
```

빠른 검사에서 APK 빌드를 생략하려면 `--skip-build`를 사용합니다. 실제 기기의 지도 통합
테스트까지 실행하려면 Client ID와 기기를 지정합니다.

```bash
NAVER_MAP_CLIENT_ID=<client-id> \
  ./scripts/test-frontend.sh --device <device-id>
```

개별 명령은 다음과 같습니다.

```powershell
C:\Users\Twibap\flutter\bin\flutter.bat analyze
C:\Users\Twibap\flutter\bin\flutter.bat test
```

### Native map integration tests

The native map tests verify that shop markers are registered on the platform
map and that dense markers merge at zoom 15 and split back into individual
markers at zoom 21. Run them with a NAVER Dynamic Map client ID:

```bash
flutter test integration_test/map_interaction_test.dart \
  -d <device-id> \
  --dart-define="NAVER_MAP_CLIENT_ID=$NAVER_MAP_CLIENT_ID"
```

Use `flutter devices` to find an Android device or iOS simulator ID.
