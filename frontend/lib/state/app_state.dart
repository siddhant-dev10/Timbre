import 'package:flutter/foundation.dart';

import '../core/config/app_config.dart';
import '../models/citizen.dart';
import '../models/eligibility_result.dart';
import '../models/call_job.dart';
import '../models/service_scheme.dart';
import '../services/citizen_repository.dart';
import '../services/mock_citizen_repository.dart';
import '../services/api_citizen_repository.dart';
import '../services/backend_health.dart';

/// Central observable state manager for Timbre.
class AppState extends ChangeNotifier {
  late CitizenRepository _repository;
  bool _useDemoMode = true;

  // Citizens state
  List<Citizen> _citizens = [];
  int _citizensTotal = 0;
  int _citizensOffset = 0;
  static const int _citizensPageSize = 100;
  bool _isLoadingCitizens = false;
  String? _citizensError;
  String _searchQuery = '';
  bool _showArchived = false;
  String _sortBy = 'id';
  String _sortOrder = 'asc';
  Citizen? _selectedCitizen;

  // Eligibility state
  final Map<String, List<EligibilityResult>> _eligibilityCache = {};
  bool _isLoadingEligibility = false;
  String? _eligibilityError;

  // Calls state
  List<CallJob> _callJobs = [];
  bool _isLoadingCalls = false;
  String? _callsError;

  // Services directory
  List<ServiceScheme> _services = [];

  // Life-event simulation result
  CitizenDobUpdateResult? _lastSimulationResult;
  bool _isSimulating = false;
  String? _simulationError;

  // Backend Health
  BackendHealth _backendHealth = BackendHealth.demoMode(AppConfig.backendUrl);

  AppState({CitizenRepository? repository}) {
    if (repository != null) {
      _repository = repository;
      _useDemoMode = repository.isMock;
    } else {
      _useDemoMode = AppConfig.isDemoMode;
      _repository = _useDemoMode
          ? MockCitizenRepository()
          : ApiCitizenRepository();
    }
  }

  // Getters
  bool get isDemoMode => _useDemoMode;
  CitizenRepository get repository => _repository;
  List<Citizen> get citizens => _citizens;
  int get citizensTotal => _citizensTotal;
  int get citizensOffset => _citizensOffset;
  bool get canLoadNextCitizenPage => _citizensOffset + _citizens.length < _citizensTotal;
  bool get isLoadingCitizens => _isLoadingCitizens;
  String? get citizensError => _citizensError;
  String get searchQuery => _searchQuery;
  bool get showArchived => _showArchived;
  String get sortBy => _sortBy;
  Citizen? get selectedCitizen => _selectedCitizen;

  bool get isLoadingEligibility => _isLoadingEligibility;
  String? get eligibilityError => _eligibilityError;

  List<CallJob> get callJobs => _callJobs;
  bool get isLoadingCalls => _isLoadingCalls;
  String? get callsError => _callsError;

  List<ServiceScheme> get services => _services;

  CitizenDobUpdateResult? get lastSimulationResult => _lastSimulationResult;
  bool get isSimulating => _isSimulating;
  String? get simulationError => _simulationError;

  BackendHealth get backendHealth => _backendHealth;

  List<EligibilityResult> getEligibilityForSelected() {
    if (_selectedCitizen == null) return [];
    return _eligibilityCache[_selectedCitizen!.id] ?? [];
  }

  Future<void> init() async {
    await checkBackendHealth();
    await loadCitizens();
    await loadCallJobs();
    await loadServices();
  }

  Future<void> setMode(bool demoMode) async {
    _useDemoMode = demoMode;
    AppConfig.isDemoMode = demoMode;
    _repository = demoMode ? MockCitizenRepository() : ApiCitizenRepository();
    _selectedCitizen = null;
    _eligibilityCache.clear();
    _lastSimulationResult = null;
    notifyListeners();
    await init();
  }

  Future<void> setBackendUrl(String url) async {
    AppConfig.backendUrl = url;
    if (!_useDemoMode) {
      _repository = ApiCitizenRepository();
    }
    notifyListeners();
    await checkBackendHealth();
  }

  Future<void> checkBackendHealth() async {
    _backendHealth = BackendHealth.checking(AppConfig.backendUrl);
    notifyListeners();
    try {
      if (_useDemoMode) {
        _backendHealth = BackendHealth.demoMode(AppConfig.backendUrl);
      } else {
        _backendHealth = await _repository.checkHealth();
      }
    } catch (e) {
      _backendHealth = BackendHealth.disconnected(
        AppConfig.backendUrl,
        e.toString(),
      );
    }
    notifyListeners();
  }

  Future<void> loadCitizens() async {
    _isLoadingCitizens = true;
    _citizensError = null;
    notifyListeners();

    try {
      _citizens = await _repository.getCitizens(limit: _citizensPageSize, offset: _citizensOffset, query: _searchQuery, includeArchived: _showArchived, archivedOnly: _showArchived, sortBy: _sortBy, sortOrder: _sortOrder);
      _citizensTotal = _repository.lastCitizenTotal;
      if (_selectedCitizen != null) {
        // Refresh selected citizen reference if present
        final match = _citizens
            .where((c) => c.id == _selectedCitizen!.id)
            .toList();
        if (match.isNotEmpty) {
          _selectedCitizen = match.first;
        }
      } else if (_citizens.isNotEmpty) {
        _selectedCitizen = _citizens.first;
        await loadEligibilityForCitizen(_selectedCitizen!.id);
      }
    } catch (e) {
      _citizensError = e.toString();
    } finally {
      _isLoadingCitizens = false;
      notifyListeners();
    }
  }

  Future<void> setShowArchived(bool value) async {
    _showArchived = value;
    _citizensOffset = 0;
    _selectedCitizen = null;
    notifyListeners();
    await loadCitizens();
  }

  Future<Citizen> createCitizen(Map<String, dynamic> payload) async {
    final citizen = await _repository.createCitizen(payload);
    _citizensOffset = 0;
    await loadCitizens();
    await selectCitizen(citizen);
    return citizen;
  }

  Future<Citizen> updateCitizen(String id, Map<String, dynamic> payload) async {
    final citizen = await _repository.updateCitizen(id, payload);
    await loadCitizens();
    await selectCitizen(citizen);
    return citizen;
  }

  Future<Citizen> archiveCitizen(String id) async {
    final citizen = await _repository.archiveCitizen(id);
    if (_selectedCitizen?.id == id) _selectedCitizen = null;
    if (_citizensOffset >= _citizensTotal - 1) _citizensOffset = (_citizensOffset - _citizensPageSize).clamp(0, 1 << 31);
    await loadCitizens();
    return citizen;
  }

  Future<Map<String, dynamic>> importRecords(String path) async {
    final result = await _repository.importRecords(path);
    if (result['committed'] == true) { _citizensOffset = 0; await loadCitizens(); }
    return result;
  }

  Future<String> exportRecords(String format) => _repository.exportRecords(format);

  void setSearchQuery(String query) {
    _searchQuery = query;
    _citizensOffset = 0;
    loadCitizens();
  }

  Future<void> goToCitizenPage(int offset) async {
    _citizensOffset = offset.clamp(0, _citizensTotal == 0 ? 0 : _citizensTotal - 1);
    _selectedCitizen = null;
    await loadCitizens();
  }

  Future<void> setCitizenSort(String value) async {
    if (value == _sortBy) {
      _sortOrder = _sortOrder == 'asc' ? 'desc' : 'asc';
    } else {
      _sortBy = value;
      _sortOrder = 'asc';
    }
    _citizensOffset = 0;
    await loadCitizens();
  }

  Future<void> selectCitizen(Citizen citizen) async {
    _selectedCitizen = citizen;
    notifyListeners();
    await loadEligibilityForCitizen(citizen.id);
  }

  Future<void> loadEligibilityForCitizen(String citizenId) async {
    _isLoadingEligibility = true;
    _eligibilityError = null;
    notifyListeners();

    try {
      final results = await _repository.evaluateEligibility(citizenId);
      _eligibilityCache[citizenId] = results;
    } catch (e) {
      _eligibilityError = e.toString();
    } finally {
      _isLoadingEligibility = false;
      notifyListeners();
    }
  }

  Future<void> simulateDobChange(String citizenId, DateTime newDob) async {
    _isSimulating = true;
    _simulationError = null;
    _lastSimulationResult = null;
    notifyListeners();

    try {
      final result = await _repository.updateCitizenDob(citizenId, newDob);
      _lastSimulationResult = result;

      // Update selected citizen and citizens list
      final index = _citizens.indexWhere((c) => c.id == citizenId);
      if (index != -1) {
        _citizens[index] = result.citizen;
      }
      if (_selectedCitizen?.id == citizenId) {
        _selectedCitizen = result.citizen;
      }

      // Re-evaluate eligibility
      await loadEligibilityForCitizen(citizenId);
      // Refresh call jobs queue
      await loadCallJobs();
    } catch (e) {
      _simulationError = e.toString();
    } finally {
      _isSimulating = false;
      notifyListeners();
    }
  }

  Future<void> loadCallJobs() async {
    _isLoadingCalls = true;
    _callsError = null;
    notifyListeners();

    try {
      _callJobs = await _repository.getCallJobs();
    } catch (e) {
      _callsError = e.toString();
    } finally {
      _isLoadingCalls = false;
      notifyListeners();
    }
  }

  Future<void> scheduleCall(String citizenId, String triggerEvent) async {
    try {
      await _repository.scheduleCallJob(citizenId, triggerEvent);
      await loadCallJobs();
    } catch (e) {
      _callsError = e.toString();
      notifyListeners();
      rethrow;
    }
  }

  Future<CallJob> createDryRunCall({
    required String citizenId,
    required String testRecipientNumber,
  }) async {
    try {
      final job = await _repository.createDryRunCall(
        citizenId: citizenId,
        testRecipientNumber: testRecipientNumber,
      );
      await loadCallJobs();
      return job;
    } catch (e) {
      _callsError = e.toString();
      notifyListeners();
      rethrow;
    }
  }

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
    try {
      final job = await _repository.createApprovedTestCall(
        citizenId: citizenId,
        testRecipientNumber: testRecipientNumber,
        language: language,
        recipientHasConsented: recipientHasConsented,
        scriptReviewed: scriptReviewed,
        aiDisclosureConfirmed: aiDisclosureConfirmed,
        callerIdReviewed: callerIdReviewed,
        confirmSingleCall: confirmSingleCall,
        confirmationPhrase: confirmationPhrase,
      );
      await loadCallJobs();
      return job;
    } catch (e) {
      _callsError = e.toString();
      notifyListeners();
      rethrow;
    }
  }

  Future<CallJob> refreshCallJobStatus(String callId) async {
    final job = await _repository.refreshCallJobStatus(callId);
    await loadCallJobs();
    return job;
  }

  Future<CallJob> stopQueuedCall(String callId) async {
    final job = await _repository.stopQueuedCall(callId);
    await loadCallJobs();
    return job;
  }

  Future<void> loadServices() async {
    try {
      _services = await _repository.getServices();
      notifyListeners();
    } catch (_) {}
  }
}
