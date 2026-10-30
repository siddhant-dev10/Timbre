/// Centralized configuration for Timbre frontend.
/// All backend endpoints, timeouts, and operational modes are configurable here.
class AppConfig {
  /// Backend URL can be supplied at build/run time, for example:
  /// Optional local backend override. The default always targets this Mac.
  static const String defaultBackendUrl = String.fromEnvironment(
    'TIMBRE_API_BASE_URL',
    defaultValue: 'http://localhost:8000/api/v1',
  );

  /// Active backend URL (can be updated at runtime via the UI).
  static String backendUrl = defaultBackendUrl;

  /// Default timeout for HTTP requests.
  static const Duration requestTimeout = Duration(seconds: 5);
  static const Duration callRequestTimeout = Duration(seconds: 45);

  /// Operational data mode.
  /// Compile-time configuration: Pass `--dart-define=TIMBRE_DEMO_MODE=true` to enable mock demo mode.
  /// When omitted or false, the application connects directly to the local FastAPI backend.
  static const bool defaultDemoMode = bool.fromEnvironment(
    'TIMBRE_DEMO_MODE',
    defaultValue: false,
  );

  /// Active operational mode (can be toggled at runtime via the UI).
  static bool isDemoMode = defaultDemoMode;

  /// Invariant: Hard safety flag enforcing fictional data indicators in the UI.
  static const bool enforceFictionalNotice = true;
}
