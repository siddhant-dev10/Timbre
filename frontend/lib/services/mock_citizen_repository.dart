import 'dart:async';

import '../models/citizen.dart';
import '../models/eligibility_result.dart';
import '../models/call_job.dart';
import '../models/call_event.dart';
import '../models/service_scheme.dart';
import 'backend_health.dart';
import 'citizen_repository.dart';

/// Isolated, local demo mock repository with synthetic data.
/// Isolated synthetic demo data; no backend or provider credentials are required.
class MockCitizenRepository implements CitizenRepository {
  @override
  bool get isMock => true;

  @override
  int get lastCitizenTotal => _citizens.length;

  @override
  String get dataSourceDescription =>
      'Demo Mock Provider (In-Memory Synthetic Data)';

  // Curated statutory schemes
  static final List<ServiceScheme> _schemes = [
    const ServiceScheme(
      id: 'scheme-001',
      serviceCode: 'VOTER_ID_ECI',
      serviceName: 'Voter Registration (Form 6)',
      administeringBody: 'Election Commission of India',
      officialPortalUrl: 'https://voters.eci.gov.in/',
      statutoryFeeInr: 0.00,
      applicationMode: 'ONLINE',
      descriptionEnglish: 'Statutory voter registration for Indian citizens who have attained 18 years of age.',
      descriptionHinglish:
          '18 saal ke nagrikon ke liye muft online voter card registration.',
      minAge: 18,
      requiredDocs: [
        'Recent passport photograph',
        'Proof of Age (Birth Certificate / Aadhaar / 10th Marksheet)',
        'Proof of Ordinary Residence (Electricity Bill / Passbook)',
      ],
    ),
    const ServiceScheme(
      id: 'scheme-002',
      serviceCode: 'LEARNERS_LICENCE_MORTH',
      serviceName: "Learner's Driving Licence",
      administeringBody: 'Ministry of Road Transport and Highways (Parivahan)',
      officialPortalUrl: 'https://parivahan.gov.in/',
      statutoryFeeInr: 200.00,
      applicationMode: 'ONLINE',
      descriptionEnglish: 'Preliminary licence allowing learner drivers to practice on public roads.',
      descriptionHinglish: 'Aadhaar e-KYC ke sath bina RTO jaye ghar baithe online learner test.',
      minAge: 18,
      requiredDocs: [
        'Aadhaar Card with mobile linking',
        'Proof of Address',
        'Medical self-declaration Form 1',
      ],
    ),
    const ServiceScheme(
      id: 'scheme-003',
      serviceCode: 'AYUSHMAN_BHARAT_PMJAY',
      serviceName: 'Pradhan Mantri Jan Arogya Yojana',
      administeringBody: 'National Health Authority (NHA)',
      officialPortalUrl: 'https://pmjay.gov.in/',
      statutoryFeeInr: 0.00,
      applicationMode: 'HYBRID',
      descriptionEnglish: 'Cashless secondary and tertiary health coverage up to ₹5 lakh per family per year.',
      descriptionHinglish: 'Bimar hone par ₹5 lakh tak ka muft ilaj sarkari aur empanelled private hospitals mein.',
      minAge: 0,
      requiredDocs: ['Ration Card / SECC Name Match', 'Aadhaar Card'],
    ),
  ];

  // In-memory synthetic citizen records (100% fictional)
  late List<Citizen> _citizens;
  late List<CallJob> _callJobs;

  final Duration delay;

  MockCitizenRepository({this.delay = Duration.zero}) {
    final now = DateTime.now();

    // Generate reference dates:
    // Aarav: 17 years and 11 months old (eligible for turning 18 simulation!)
    final aaravDob = DateTime(now.year - 18, now.month + 1, 15);

    _citizens = [
      Citizen(
        id: 'cit-001',
        firstName: 'Aarav',
        lastName: 'Sharma',
        dateOfBirth: aaravDob,
        gender: 'MALE',
        phoneNumber: '+91-99999-00012',
        state: 'Uttar Pradesh',
        district: 'Lucknow',
        pincode: '226001',
        simulatedIncomeBracket: 'MIDDLE',
        isFictional: true,
      ),
      Citizen(
        id: 'cit-002',
        firstName: 'Priya',
        lastName: 'Patel',
        dateOfBirth: DateTime(now.year - 19, 4, 12),
        gender: 'FEMALE',
        phoneNumber: '+91-99999-00013',
        state: 'Gujarat',
        district: 'Ahmedabad',
        pincode: '380001',
        simulatedIncomeBracket: 'LOW',
        isFictional: true,
      ),
      Citizen(
        id: 'cit-003',
        firstName: 'Rajesh',
        lastName: 'Kumar',
        dateOfBirth: DateTime(now.year - 42, 8, 20),
        gender: 'MALE',
        phoneNumber: '+91-99999-00014',
        state: 'Bihar',
        district: 'Patna',
        pincode: '800001',
        simulatedIncomeBracket: 'LOW',
        isFictional: true,
      ),
      Citizen(
        id: 'cit-004',
        firstName: 'Ananya',
        lastName: 'Iyer',
        dateOfBirth: DateTime(now.year - 17, now.month, now.day - 1),
        gender: 'FEMALE',
        phoneNumber: '+91-99999-00015',
        state: 'Tamil Nadu',
        district: 'Chennai',
        pincode: '600001',
        simulatedIncomeBracket: 'MIDDLE',
        isFictional: true,
      ),
      Citizen(
        id: 'cit-005',
        firstName: 'Vikram',
        lastName: 'Singh',
        dateOfBirth: DateTime(now.year - 24, 11, 5),
        gender: 'MALE',
        phoneNumber: '+91-99999-00016',
        state: 'Rajasthan',
        district: 'Jaipur',
        pincode: '302001',
        simulatedIncomeBracket: 'MIDDLE',
        isFictional: true,
      ),
      Citizen(
        id: 'cit-006',
        firstName: 'Fatima',
        lastName: 'Sheikh',
        dateOfBirth: DateTime(now.year - 21, 2, 18),
        gender: 'FEMALE',
        phoneNumber: '+91-99999-00017',
        state: 'Maharashtra',
        district: 'Mumbai',
        pincode: '400001',
        simulatedIncomeBracket: 'HIGH',
        isFictional: true,
      ),
      Citizen(
        id: 'cit-007',
        firstName: 'Rohan',
        lastName: 'Gupta',
        dateOfBirth: DateTime(now.year - 16, 6, 25),
        gender: 'MALE',
        phoneNumber: '+91-99999-00018',
        state: 'Delhi',
        district: 'New Delhi',
        pincode: '110001',
        simulatedIncomeBracket: 'MIDDLE',
        isFictional: true,
      ),
      Citizen(
        id: 'cit-008',
        firstName: 'Pooja',
        lastName: 'Joshi',
        dateOfBirth: DateTime(now.year - 18, now.month - 2, 10),
        gender: 'FEMALE',
        phoneNumber: '+91-99999-00019',
        state: 'Uttarakhand',
        district: 'Dehradun',
        pincode: '248001',
        simulatedIncomeBracket: 'MIDDLE',
        isFictional: true,
      ),
    ];

    // Completed sample call job demonstrating Hinglish transcript and telemetry
    _callJobs = [
      CallJob(
        id: 'job-demo-001',
        citizenId: 'cit-002',
        citizenName: 'Priya Patel',
        triggerEvent: 'MILESTONE_AGE_18',
        jobStatus: 'COMPLETED',
        idempotencyKey: 'CALL_AGE18_cit-002_${now.year}',
        attemptCount: 1,
        scheduledAt: now.subtract(const Duration(hours: 3)),
        durationSeconds: 114,
        transcriptEvents: [
          CallEvent(
            id: 'ev-1',
            speaker: 'AI_AGENT',
            transcriptSegment: 'Namaste Priya ji! Main Timbre se bol rahi hoon, ek automated AI government service sahayak. Aap haal hi mein 18 saal ki hui hain, badhai ho!',
            timestamp: now.subtract(const Duration(hours: 3, seconds: 110)),
            latencyMs: 320,
          ),
          CallEvent(
            id: 'ev-2',
            speaker: 'CITIZEN',
            transcriptSegment:
                'Haan ji namaste. Is call ke baare mein batayein?',
            timestamp: now.subtract(const Duration(hours: 3, seconds: 95)),
            latencyMs: 180,
          ),
          CallEvent(
            id: 'ev-3',
            speaker: 'AI_AGENT',
            transcriptSegment: 'Ji, aap ab Voter ID aur Learner Driving Licence ke liye qualify karti hain. Dono ke official portals par online apply karna bilkul aasan hai.',
            timestamp: now.subtract(const Duration(hours: 3, seconds: 70)),
            latencyMs: 290,
          ),
          CallEvent(
            id: 'ev-4',
            speaker: 'CITIZEN',
            transcriptSegment: 'Voter ID ke liye koi fees lagti hai kya?',
            timestamp: now.subtract(const Duration(hours: 3, seconds: 50)),
            latencyMs: 210,
          ),
          CallEvent(
            id: 'ev-5',
            speaker: 'AI_AGENT',
            transcriptSegment: 'Nahi Priya ji, Election Commission of India ke portal voters.eci.gov.in par Form 6 bharna bilkul free hai. Koi fee nahi hoti.',
            timestamp: now.subtract(const Duration(hours: 3, seconds: 30)),
            latencyMs: 310,
          ),
        ],
      ),
    ];
  }

  @override
  Future<List<Citizen>> getCitizens({
    int limit = 20,
    int offset = 0,
    String? query,
    bool includeArchived = false,
    bool archivedOnly = false,
    String sortBy = 'id',
    String sortOrder = 'asc',
  }) async {
    if (delay > Duration.zero) await Future.delayed(delay);
    var results = List<Citizen>.from(_citizens);
    if (query != null && query.trim().isNotEmpty) {
      final q = query.trim().toLowerCase();
      results = results.where((c) {
        return c.fullName.toLowerCase().contains(q) ||
            c.state.toLowerCase().contains(q) ||
            c.district.toLowerCase().contains(q) ||
            c.phoneNumber.contains(q);
      }).toList();
    }
    return results;
  }

  @override
  Future<Citizen> getCitizenById(String id) async {
    if (delay > Duration.zero) await Future.delayed(delay);
    final found = _citizens.firstWhere(
      (c) => c.id == id,
      orElse: () =>
          throw Exception('Citizen with ID $id not found in mock store.'),
    );
    return found;
  }

  @override
  Future<Citizen> createCitizen(Map<String, dynamic> payload) async => throw UnsupportedError('Persistent record management requires backend mode.');

  @override
  Future<Citizen> updateCitizen(String id, Map<String, dynamic> payload) async => throw UnsupportedError('Persistent record management requires backend mode.');

  @override
  Future<Citizen> archiveCitizen(String id) async => throw UnsupportedError('Persistent record management requires backend mode.');

  @override
  Future<Citizen> restoreCitizen(String id) async => throw UnsupportedError('Persistent record management requires backend mode.');

  @override
  Future<Map<String, dynamic>> importRecords(String path) async => throw UnsupportedError('Persistent record management requires backend mode.');

  @override
  Future<String> exportRecords(String format) async => throw UnsupportedError('Persistent record management requires backend mode.');

  @override
  Future<CitizenDobUpdateResult> updateCitizenDob(
    String citizenId,
    DateTime newDob,
  ) async {
    if (delay > Duration.zero) await Future.delayed(delay);
    final index = _citizens.indexWhere((c) => c.id == citizenId);
    if (index == -1) {
      throw Exception('Citizen $citizenId not found');
    }

    final oldCitizen = _citizens[index];
    final prevAge = oldCitizen.age;
    final updatedCitizen = oldCitizen.copyWith(dateOfBirth: newDob);
    _citizens[index] = updatedCitizen;
    final newAge = updatedCitizen.age;

    String? eventDetected;
    CallJob? generatedJob;

    // Detect Age 18 Milestone crossing & enforce idempotency
    if (newAge >= 18) {
      if (prevAge < 18) {
        eventDetected = 'MILESTONE_AGE_18';
      }
      final year = DateTime.now().year;
      final idempotencyKey = 'CALL_AGE18_${updatedCitizen.id}_$year';

      // Duplicate prevention: check if job already exists
      final existing = _callJobs
          .where((j) => j.idempotencyKey == idempotencyKey)
          .toList();
      if (existing.isEmpty) {
        generatedJob = CallJob(
          id: 'job-${DateTime.now().millisecondsSinceEpoch}',
          citizenId: updatedCitizen.id,
          citizenName: updatedCitizen.fullName,
          triggerEvent: eventDetected ?? 'MILESTONE_AGE_18',
          jobStatus: 'QUEUED',
          idempotencyKey: idempotencyKey,
          scheduledAt: DateTime.now(),
        );
        _callJobs.insert(0, generatedJob);
      } else {
        generatedJob = existing.first;
      }
    }

    return CitizenDobUpdateResult(
      citizen: updatedCitizen,
      previousAge: prevAge,
      newAge: newAge,
      eventDetected: eventDetected,
      generatedCallJob: generatedJob,
    );
  }

  @override
  Future<List<EligibilityResult>> getEligibility(String citizenId) async {
    return evaluateEligibility(citizenId);
  }

  @override
  Future<List<EligibilityResult>> evaluateEligibility(String citizenId) async {
    if (delay > Duration.zero) await Future.delayed(delay);
    final citizen = await getCitizenById(citizenId);
    final results = <EligibilityResult>[];

    for (final scheme in _schemes) {
      final isAgeEligible =
          citizen.age >= scheme.minAge &&
          (scheme.maxAge == null || citizen.age <= scheme.maxAge!);

      String reason;
      List<String> missing = [];

      if (scheme.serviceCode == 'VOTER_ID_ECI') {
        if (citizen.age >= 18) {
          reason =
              'Citizen is ${citizen.age} years old (>= 18 threshold). Eligible for electoral roll inclusion.';
        } else {
          reason =
              'Citizen is ${citizen.age} years old. Must be at least 18 years of age.';
          missing.add('Minimum age of 18 years');
        }
      } else if (scheme.serviceCode == 'LEARNERS_LICENCE_MORTH') {
        if (citizen.age >= 18) {
          reason =
              'Citizen is ${citizen.age} years old (>= 18 threshold). Eligible for online Aadhaar e-KYC Learner Licence.';
        } else {
          reason =
              'Citizen is ${citizen.age} years old. Motor Vehicles Act mandates age >= 18 for transport vehicles.';
          missing.add('Minimum age of 18 years');
        }
      } else {
        reason = 'Eligible under universal civic welfare provisions.';
      }

      results.add(
        EligibilityResult(
          id: 'elg-${citizen.id}-${scheme.serviceCode}',
          citizenId: citizen.id,
          service: scheme,
          isEligible: isAgeEligible,
          evaluatedAt: DateTime.now(),
          qualificationReason: reason,
          missingRequirements: missing,
          notifiedStatus: isAgeEligible ? 'QUEUED' : 'PENDING',
        ),
      );
    }

    return results;
  }

  @override
  Future<List<CallJob>> getCallJobs({String? citizenId}) async {
    if (delay > Duration.zero) await Future.delayed(delay);
    if (citizenId != null) {
      return _callJobs.where((j) => j.citizenId == citizenId).toList();
    }
    return List<CallJob>.from(_callJobs);
  }

  @override
  Future<CallJob> scheduleCallJob(String citizenId, String triggerEvent) async {
    if (delay > Duration.zero) await Future.delayed(delay);
    final citizen = await getCitizenById(citizenId);
    final year = DateTime.now().year;
    final idempotencyKey = 'CALL_${triggerEvent}_${citizen.id}_$year';

    // Check duplicate
    final existing = _callJobs
        .where((j) => j.idempotencyKey == idempotencyKey)
        .toList();
    if (existing.isNotEmpty) {
      return existing.first;
    }

    final newJob = CallJob(
      id: 'job-${DateTime.now().millisecondsSinceEpoch}',
      citizenId: citizen.id,
      citizenName: citizen.fullName,
      triggerEvent: triggerEvent,
      jobStatus: 'QUEUED',
      idempotencyKey: idempotencyKey,
      scheduledAt: DateTime.now(),
    );
    _callJobs.insert(0, newJob);
    return newJob;
  }

  @override
  Future<CallJob> createDryRunCall({
    required String citizenId,
    required String testRecipientNumber,
  }) async {
    if (delay > Duration.zero) await Future.delayed(delay);
    final citizen = await getCitizenById(citizenId);
    final digits = testRecipientNumber.replaceAll(RegExp(r'\D'), '');
    final masked = digits.length >= 4
        ? '***${digits.substring(digits.length - 4)}'
        : '***';
    final now = DateTime.now();
    final job = CallJob(
      id: 'dry-run-${now.microsecondsSinceEpoch}',
      citizenId: citizen.id,
      citizenName: 'Synthetic test profile',
      triggerEvent: 'MANUAL_REVIEWED_DRY_RUN',
      jobStatus: 'COMPLETED',
      idempotencyKey: 'local-dry-run-${now.microsecondsSinceEpoch}',
      scheduledAt: now,
      recipientPhone: masked,
      transcriptEvents: [
        CallEvent(
          id: 'mock-ai-opening',
          speaker: 'AI_AGENT',
          transcriptSegment: 'Namaste, main Timbre hoon, ek AI assistant. Yeh sirf local simulated demo hai; koi call nahi ho rahi.',
          timestamp: now,
        ),
        CallEvent(
          id: 'mock-caller-question',
          speaker: 'CITIZEN',
          transcriptSegment: 'Mujhe government service ki eligibility kaise check karni chahiye?',
          timestamp: now,
        ),
        CallEvent(
          id: 'mock-ai-answer',
          speaker: 'AI_AGENT',
          transcriptSegment: 'Official portal par current requirements verify karein. Yeh mock transcript hai, kisi AI provider ya phone network se contact nahi hua.',
          timestamp: now,
        ),
      ],
    );
    _callJobs.insert(0, job);
    return job;
  }

  @override
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
  }) async {
    throw StateError('Live calls are unavailable in isolated mock mode.');
  }

  @override
  Future<CallJob> refreshCallJobStatus(String callId) async {
    final matches = _callJobs.where((job) => job.id == callId);
    if (matches.isEmpty) throw StateError('Call job not found.');
    return matches.first;
  }

  @override
  Future<CallJob> stopQueuedCall(String callId) async {
    final index = _callJobs.indexWhere((job) => job.id == callId);
    if (index < 0) throw StateError('Call job not found.');
    final old = _callJobs[index];
    final stopped = CallJob(
      id: old.id,
      citizenId: old.citizenId,
      citizenName: old.citizenName,
      triggerEvent: old.triggerEvent,
      jobStatus: 'STOPPED',
      idempotencyKey: old.idempotencyKey,
      attemptCount: old.attemptCount,
      scheduledAt: old.scheduledAt,
      durationSeconds: old.durationSeconds,
      transcriptEvents: old.transcriptEvents,
      isRealCall: old.isRealCall,
      recipientPhone: old.recipientPhone,
      bolnaExecutionId: old.bolnaExecutionId,
    );
    _callJobs[index] = stopped;
    return stopped;
  }

  @override
  Future<List<ServiceScheme>> getServices() async {
    return List<ServiceScheme>.from(_schemes);
  }

  @override
  Future<BackendHealth> checkHealth() async {
    if (delay > Duration.zero) await Future.delayed(delay);
    return BackendHealth.demoMode('local://in-memory-mock');
  }
}
