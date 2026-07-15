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

Connect the in-app incorrect-info report button by passing a support mailbox:

```powershell
C:\Users\Twibap\flutter\bin\flutter.bat run `
  --dart-define=NAVER_MAP_CLIENT_ID=your-client-id `
  --dart-define=API_BASE_URL=http://192.168.0.10:8000 `
  --dart-define=SUPPORT_EMAIL=support@example.com
```

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

```powershell
C:\Users\Twibap\flutter\bin\flutter.bat analyze
C:\Users\Twibap\flutter\bin\flutter.bat test
```
