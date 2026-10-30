enum BackendConnectionState { connected, disconnected, checking, demoOnly }

/// Represents the connection health of the Mac-local FastAPI backend.
class BackendHealth {
  final BackendConnectionState state;
  final String message;
  final String hostUrl;
  final int latencyMs;
  final DateTime checkedAt;
  final String? version;
  final bool bolnaTestCallReady;
  final Map<String, String> integrations;

  const BackendHealth({
    required this.state,
    required this.message,
    required this.hostUrl,
    this.latencyMs = 0,
    required this.checkedAt,
    this.version,
    this.bolnaTestCallReady = false,
    this.integrations = const {},
  });

  bool get isConnected => state == BackendConnectionState.connected;
  bool get isDemoOnly => state == BackendConnectionState.demoOnly;

  factory BackendHealth.demoMode(String url) {
    return BackendHealth(
      state: BackendConnectionState.demoOnly,
      message: 'Running in isolated local demo mode',
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
    bool bolnaTestCallReady = false,
    Map<String, String> integrations = const {},
  ]) {
    return BackendHealth(
      state: BackendConnectionState.connected,
      message: 'Connected to FastAPI backend ($latencyMs ms)',
      hostUrl: url,
      latencyMs: latencyMs,
      checkedAt: DateTime.now(),
      version: version ?? '1.0.0',
      bolnaTestCallReady: bolnaTestCallReady,
      integrations: integrations,
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
