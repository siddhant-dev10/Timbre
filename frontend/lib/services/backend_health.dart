enum BackendConnectionState { connected, disconnected, checking, demoOnly }

/// Represents the connection health of the ASUS FastAPI backend.
class BackendHealth {
  final BackendConnectionState state;
  final String message;
  final String hostUrl;
  final int latencyMs;
  final DateTime checkedAt;
  final String? version;

  const BackendHealth({
    required this.state,
    required this.message,
    required this.hostUrl,
    this.latencyMs = 0,
    required this.checkedAt,
    this.version,
  });

  bool get isConnected => state == BackendConnectionState.connected;
  bool get isDemoOnly => state == BackendConnectionState.demoOnly;

  factory BackendHealth.demoMode(String url) {
    return BackendHealth(
      state: BackendConnectionState.demoOnly,
      message: 'Running in isolated local demo mode (ASUS backend offline)',
      hostUrl: url,
      checkedAt: DateTime.now(),
      version: 'Demo Mock v1.0',
    );
  }

  factory BackendHealth.checking(String url) {
    return BackendHealth(
      state: BackendConnectionState.checking,
      message: 'Connecting to backend...',
      hostUrl: url,
      checkedAt: DateTime.now(),
    );
  }

  factory BackendHealth.connected(
    String url,
    int latencyMs, [
    String? version,
  ]) {
    return BackendHealth(
      state: BackendConnectionState.connected,
      message: 'Connected to FastAPI backend ($latencyMs ms)',
      hostUrl: url,
      latencyMs: latencyMs,
      checkedAt: DateTime.now(),
      version: version ?? '1.0.0',
    );
  }

  factory BackendHealth.disconnected(String url, String error) {
    return BackendHealth(
      state: BackendConnectionState.disconnected,
      message: 'Cannot reach backend: $error',
      hostUrl: url,
      checkedAt: DateTime.now(),
    );
  }
}
