import 'call_event.dart';

/// Represents a simulated outbound voice call job.
class CallJob {
  final String id;
  final String citizenId;
  final String citizenName;
  final String triggerEvent; // e.g. MILESTONE_AGE_18
  final String
  jobStatus; // QUEUED, IN_PROGRESS, COMPLETED, FAILED, RETRY_SCHEDULED
  final String idempotencyKey;
  final int attemptCount;
  final DateTime scheduledAt;
  final int durationSeconds;
  final List<CallEvent> transcriptEvents;
  final bool isRealCall;
  final String recipientPhone;
  final String? bolnaExecutionId;

  const CallJob({
    required this.id,
    required this.citizenId,
    required this.citizenName,
    required this.triggerEvent,
    required this.jobStatus,
    required this.idempotencyKey,
    this.attemptCount = 0,
    required this.scheduledAt,
    this.durationSeconds = 0,
    this.transcriptEvents = const [],
    this.isRealCall = false,
    this.recipientPhone = '***',
    this.bolnaExecutionId,
  });

  bool get isCompleted => jobStatus == 'COMPLETED';
  bool get isQueued => jobStatus == 'QUEUED';
  bool get isInProgress => jobStatus == 'IN_PROGRESS';
  bool get isFailed => jobStatus == 'FAILED';

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'citizen_id': citizenId,
      'citizen_name': citizenName,
      'trigger_event': triggerEvent,
      'job_status': jobStatus,
      'idempotency_key': idempotencyKey,
      'attempt_count': attemptCount,
      'scheduled_at': scheduledAt.toIso8601String(),
      'duration_seconds': durationSeconds,
      'transcript_events': transcriptEvents.map((e) => e.toJson()).toList(),
      'is_real_call': isRealCall,
      'recipient_phone': recipientPhone,
      'bolna_execution_id': bolnaExecutionId,
    };
  }

  factory CallJob.fromJson(Map<String, dynamic> json) {
    return CallJob(
      id: json['id'] as String,
      citizenId: json['citizen_id'] as String,
      citizenName: json['citizen_name'] as String? ?? 'Synthetic Citizen',
      triggerEvent: json['trigger_event'] as String? ?? 'MANUAL_TRIGGER',
      jobStatus: json['job_status'] as String? ?? 'QUEUED',
      idempotencyKey: json['idempotency_key'] as String? ?? '',
      attemptCount: json['attempt_count'] as int? ?? 0,
      scheduledAt: DateTime.parse(json['scheduled_at'] as String),
      durationSeconds: json['duration_seconds'] as int? ?? 0,
      transcriptEvents:
          (json['transcript_events'] as List<dynamic>?)
              ?.map((e) => CallEvent.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
      isRealCall: json['is_real_call'] as bool? ?? false,
      recipientPhone: json['recipient_phone'] as String? ?? '***',
      bolnaExecutionId: json['bolna_execution_id'] as String?,
    );
  }
}
