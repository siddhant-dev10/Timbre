import '../models/citizen.dart';
import '../models/eligibility_result.dart';
import '../models/call_job.dart';
import '../models/service_scheme.dart';
import 'backend_health.dart';

class CitizenDobUpdateResult {
  final Citizen citizen;
  final int previousAge;
  final int newAge;
  final String? eventDetected; // e.g. MILESTONE_AGE_18
  final CallJob? generatedCallJob;

  const CitizenDobUpdateResult({
    required this.citizen,
    required this.previousAge,
    required this.newAge,
    this.eventDetected,
    this.generatedCallJob,
  });
}

/// Abstract contract for fetching and mutating citizen, eligibility, and call data.
abstract class CitizenRepository {
  bool get isMock;
  String get dataSourceDescription;

  Future<List<Citizen>> getCitizens({
    int limit = 20,
    int offset = 0,
    String? query,
  });
  Future<Citizen> getCitizenById(String id);
  Future<CitizenDobUpdateResult> updateCitizenDob(
    String citizenId,
    DateTime newDob,
  );
  Future<List<EligibilityResult>> getEligibility(String citizenId);
  Future<List<EligibilityResult>> evaluateEligibility(String citizenId);
  Future<List<CallJob>> getCallJobs({String? citizenId});
  Future<CallJob> scheduleCallJob(String citizenId, String triggerEvent);
  Future<List<ServiceScheme>> getServices();
  Future<BackendHealth> checkHealth();
}
