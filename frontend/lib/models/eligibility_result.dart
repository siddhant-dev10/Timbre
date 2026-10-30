import 'service_scheme.dart';

/// Represents an evaluation result for a citizen against a statutory service scheme.
class EligibilityResult {
  final String id;
  final String citizenId;
  final ServiceScheme service;
  final bool isEligible;
  final DateTime evaluatedAt;
  final String qualificationReason;
  final List<String> missingRequirements;
  final String notifiedStatus; // PENDING, QUEUED, NOTIFIED, DISMISSED

  const EligibilityResult({
    required this.id,
    required this.citizenId,
    required this.service,
    required this.isEligible,
    required this.evaluatedAt,
    required this.qualificationReason,
    this.missingRequirements = const [],
    this.notifiedStatus = 'PENDING',
  });

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'citizen_id': citizenId,
      'service': service.toJson(),
      'is_eligible': isEligible,
      'evaluated_at': evaluatedAt.toIso8601String(),
      'qualification_reason': qualificationReason,
      'missing_requirements': missingRequirements,
      'notified_status': notifiedStatus,
    };
  }

  factory EligibilityResult.fromJson(Map<String, dynamic> json) {
    return EligibilityResult(
      id: json['id'] as String,
      citizenId: json['citizen_id'] as String,
      service: ServiceScheme.fromJson(json['service'] as Map<String, dynamic>),
      isEligible: json['is_eligible'] as bool? ?? false,
      evaluatedAt: DateTime.parse(json['evaluated_at'] as String),
      qualificationReason: json['qualification_reason'] as String? ?? '',
      missingRequirements:
          (json['missing_requirements'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          const [],
      notifiedStatus: json['notified_status'] as String? ?? 'PENDING',
    );
  }
}
