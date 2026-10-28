/// Centralized configuration for Timbre frontend.
/// All backend endpoints, timeouts, and operational modes are configurable here.
class AppConfig {
  /// Backend URL can be supplied at build/run time, for example:
  /// `--dart-define=TIMBRE_BACKEND_URL=http://<ASUS_LAN_IP>:8000/api/v1`.
  /// Keep localhost as a development fallback; it is not the ASUS LAN address.
  static const String defaultBackendUrl = String.fromEnvironment(
    'TIMBRE_BACKEND_URL',
    defaultValue: 'http://localhost:8000/api/v1',
  );

  /// Active backend URL (can be updated at runtime via the UI).
  static String backendUrl = defaultBackendUrl;

  /// Default timeout for HTTP requests.
  static const Duration requestTimeout = Duration(seconds: 5);

  /// Operational data mode.
  /// When true, uses the isolated demo mock repository with synthetic records.
  static bool isDemoMode = bool.fromEnvironment(
    'TIMBRE_DEMO_MODE',
    defaultValue: true,
  );

  /// Invariant: Hard safety flag enforcing fictional data indicators in the UI.
  static const bool enforceFictionalNotice = true;
}
