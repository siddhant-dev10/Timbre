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
  int get lastCitizenTotal;
  String get dataSourceDescription;

  Future<List<Citizen>> getCitizens({
    int limit = 100,
    int offset = 0,
    String? query,
    bool includeArchived = false,
    bool archivedOnly = false,
    String sortBy = 'id',
    String sortOrder = 'asc',
  });
  Future<Citizen> getCitizenById(String id);
  Future<Citizen> createCitizen(Map<String, dynamic> payload);
  Future<Citizen> updateCitizen(String id, Map<String, dynamic> payload);
  Future<Citizen> archiveCitizen(String id);
  Future<Citizen> restoreCitizen(String id);
  Future<Map<String, dynamic>> importRecords(String path);
  Future<String> exportRecords(String format);
  Future<CitizenDobUpdateResult> updateCitizenDob(
    String citizenId,
    DateTime newDob,
  );
  Future<List<EligibilityResult>> getEligibility(String citizenId);
  Future<List<EligibilityResult>> evaluateEligibility(String citizenId);
  Future<List<CallJob>> getCallJobs({String? citizenId});
  Future<CallJob> scheduleCallJob(String citizenId, String triggerEvent);
  Future<CallJob> createDryRunCall({
    required String citizenId,
    required String testRecipientNumber,
  });
  Future<CallJob> createApprovedTestCall({
    required String citizenId,
    required String testRecipientNumber,
    required String language,
    required bool recipientHasConsented,
    required bool scriptReviewed,
    required bool aiDisclosureConfirmed,
    required bool callerIdReviewed,
    required bool confirmSingleCall,
    required String confirmationPhrase,
  });
  Future<CallJob> refreshCallJobStatus(String callId);
  Future<CallJob> stopQueuedCall(String callId);
  Future<List<ServiceScheme>> getServices();
  Future<BackendHealth> checkHealth();
}
