/// Granular conversational turn or telemetry marker in a voice call.
class CallEvent {
  final String id;
  final String speaker; // AI_AGENT, CITIZEN, SYSTEM
  final String transcriptSegment;
  final DateTime timestamp;
  final int latencyMs;

  const CallEvent({
    required this.id,
    required this.speaker,
    required this.transcriptSegment,
    required this.timestamp,
    this.latencyMs = 0,
  });

  bool get isAi => speaker == 'AI_AGENT';
  bool get isCitizen => speaker == 'CITIZEN';
  bool get isSystem => speaker == 'SYSTEM';

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'speaker': speaker,
      'transcript_segment': transcriptSegment,
      'timestamp': timestamp.toIso8601String(),
      'latency_ms': latencyMs,
    };
  }

  factory CallEvent.fromJson(Map<String, dynamic> json) {
    return CallEvent(
      id: json['id'] as String,
      speaker: json['speaker'] as String? ?? 'SYSTEM',
      transcriptSegment: json['transcript_segment'] as String? ?? '',
      timestamp: DateTime.parse(json['timestamp'] as String),
      latencyMs: json['latency_ms'] as int? ?? 0,
    );
  }
}
