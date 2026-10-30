# Timbre Flutter client

The macOS app uses synthetic demo data by default and makes no provider calls in
that mode. To connect to FastAPI running on the same Mac:

```sh
flutter pub get
flutter run -d macos --dart-define=TIMBRE_DEMO_MODE=false
```

The API base URL defaults to `http://localhost:8000/api/v1` and can be changed
in the app's connectivity settings. Provider credentials belong only in
`backend/.env`, never in Flutter build arguments. See the root [README](../README.md)
and [TECH.md](../TECH.md) for backend setup and limitations.
