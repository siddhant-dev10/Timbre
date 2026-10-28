# Timbre Flutter client

The Flutter dashboard uses synthetic demo data by default. To connect it to the
FastAPI server, obtain the ASUS's current LAN IP on the ASUS with
`hostname -I`, confirm the backend is listening on port `8000`, then start the
client with that verified address:

```sh
flutter run \
  --dart-define=TIMBRE_BACKEND_URL=http://<ASUS_LAN_IP>:8000/api/v1 \
  --dart-define=TIMBRE_DEMO_MODE=false
```

The backend URL can also be changed from the app's Backend & Connectivity
Settings. Build-time values provide the initial URL and mode; runtime settings
remain available. Do not use `localhost` on the Mac to reach the ASUS, because
it points back to the Mac itself.

The ASUS must be awake and on a reachable private network. Its backend should
bind to the LAN interface on port `8000`; Ollama should remain bound to
`127.0.0.1:11434`.
