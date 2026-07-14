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

Run on an Android emulator. The default API URL is `http://10.0.2.2:8000`:

```powershell
C:\Users\Twibap\flutter\bin\flutter.bat run
```

Override the API URL for a physical device or iOS simulator:

```powershell
C:\Users\Twibap\flutter\bin\flutter.bat run `
  --dart-define=API_BASE_URL=http://192.168.0.10:8000
```

Local cleartext HTTP is enabled only in the Android debug manifest. Production
builds must use HTTPS.

## Verify

```powershell
C:\Users\Twibap\flutter\bin\flutter.bat analyze
C:\Users\Twibap\flutter\bin\flutter.bat test
```
