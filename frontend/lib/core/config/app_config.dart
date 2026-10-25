/// Centralized configuration for Timbre frontend.
/// All backend endpoints, timeouts, and operational modes are configurable here.
class AppConfig {
  /// Default backend URL targeting FastAPI running on the local machine or ASUS TUF over LAN.
  /// Example ASUS LAN endpoint: 'http://192.168.1.100:8000/api/v1'
  static const String defaultBackendUrl = 'http://localhost:8000/api/v1';

  /// Active backend URL (can be updated at runtime via the UI).
  static String backendUrl = defaultBackendUrl;

  /// Default timeout for HTTP requests.
  static const Duration requestTimeout = Duration(seconds: 5);

  /// Operational data mode.
  /// When true, uses the isolated demo mock repository with synthetic records.
  static bool isDemoMode = true;

  /// Invariant: Hard safety flag enforcing fictional data indicators in the UI.
  static const bool enforceFictionalNotice = true;
}
