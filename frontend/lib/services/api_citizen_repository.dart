import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../core/config/app_config.dart';
import '../models/citizen.dart';
import '../models/eligibility_result.dart';
import '../models/call_job.dart';
import '../models/service_scheme.dart';
import 'backend_health.dart';
import 'citizen_repository.dart';

/// REST API client communicating with the Mac-local FastAPI backend.
class ApiCitizenRepository implements CitizenRepository {
  final http.Client _client;
  int _lastCitizenTotal = 0;

  ApiCitizenRepository({http.Client? client})
    : _client = client ?? http.Client();

  @override
  bool get isMock => false;

  @override
  int get lastCitizenTotal => _lastCitizenTotal;

  @override
  String get dataSourceDescription =>
      'Mac-local FastAPI Backend (${AppConfig.backendUrl})';

  Uri _uri(String path, [Map<String, dynamic>? queryParams]) {
    final base = AppConfig.backendUrl.replaceAll(RegExp(r'/+$'), '');
    final cleanPath = path.replaceAll(RegExp(r'^/+'), '');
    final uri = Uri.parse('$base/$cleanPath');
    if (queryParams != null && queryParams.isNotEmpty) {
      return uri.replace(
        queryParameters: queryParams.map((k, v) => MapEntry(k, v.toString())),
      );
    }
    return uri;
  }

  String _callError(http.Response response, String fallback) {
    try {
      final body = jsonDecode(response.body);
      if (body is Map<String, dynamic> && body['detail'] is String) {
        return body['detail'] as String;
      }
    } catch (_) {
      // Use a bounded, generic message when the backend response is not JSON.
    }
    return '$fallback (HTTP ${response.statusCode}).';
  }

  @override
  Future<BackendHealth> checkHealth() async {
    final stopwatch = Stopwatch()..start();
    try {
      final response = await _client
          .get(_uri('health'))
          .timeout(AppConfig.requestTimeout);
      stopwatch.stop();

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        final version = data['version'] as String? ?? '1.0.0';
        String component(String key) {
          final value = data[key];
          return value is Map ? (value['status'] as String? ?? 'unknown') : 'unknown';
        }
        return BackendHealth.connected(
          AppConfig.backendUrl,
          stopwatch.elapsedMilliseconds,
          version,
          data['bolna_test_call_ready'] as bool? ?? false,
          {
            'Database': component('database'),
            'NVIDIA AI': component('ai_provider'),
            'ElevenLabs TTS': component('elevenlabs_tts'),
            'Bolna telephony': component('bolna_voice'),
          },
        );
      } else {
        return BackendHealth.disconnected(
          AppConfig.backendUrl,
          'HTTP ${response.statusCode}: ${response.reasonPhrase}',
        );
      }
    } catch (e) {
      stopwatch.stop();
      return BackendHealth.disconnected(AppConfig.backendUrl, e.toString());
    }
  }

  @override
  Future<List<Citizen>> getCitizens({
    int limit = 100,
    int offset = 0,
    String? query,
    bool includeArchived = false,
    bool archivedOnly = false,
    String sortBy = 'id',
    String sortOrder = 'asc',
  }) async {
    final params = <String, dynamic>{'limit': limit, 'offset': offset, 'sort_by': sortBy, 'sort_order': sortOrder};
    if (includeArchived) params['include_archived'] = true;
    if (archivedOnly) params['archived_only'] = true;
    if (query != null && query.isNotEmpty) {
      params['q'] = query;
    }

    final response = await _client
        .get(_uri('citizens', params))
        .timeout(AppConfig.requestTimeout);

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      if (data is Map<String, dynamic>) _lastCitizenTotal = (data['total'] as num?)?.toInt() ?? 0;
      final list = (data is Map && data.containsKey('citizens'))
          ? data['citizens'] as List<dynamic>
          : data as List<dynamic>;
      return list
          .map((e) => Citizen.fromJson(e as Map<String, dynamic>))
          .toList();
    } else {
      throw Exception('Failed to load citizens: HTTP ${response.statusCode}');
    }
  }

  @override
  Future<Citizen> getCitizenById(String id) async {
    final response = await _client
        .get(_uri('citizens/$id'))
        .timeout(AppConfig.requestTimeout);

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      return Citizen.fromJson(data);
    } else {
      throw Exception('Citizen $id not found: HTTP ${response.statusCode}');
    }
  }

  @override
  Future<Citizen> createCitizen(Map<String, dynamic> payload) async {
    final response = await _client.post(_uri('citizens'), headers: {'Content-Type': 'application/json'}, body: jsonEncode(payload)).timeout(AppConfig.requestTimeout);
    if (response.statusCode == 201) return Citizen.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
    throw Exception(_callError(response, 'Record could not be created'));
  }

  @override
  Future<Citizen> updateCitizen(String id, Map<String, dynamic> payload) async {
    final response = await _client.patch(_uri('citizens/$id'), headers: {'Content-Type': 'application/json'}, body: jsonEncode(payload)).timeout(AppConfig.requestTimeout);
    if (response.statusCode == 200) return getCitizenById(id);
    throw Exception(_callError(response, 'Record could not be updated'));
  }

  Future<Citizen> _archiveAction(String id, String action) async {
    final response = await _client.post(_uri('citizens/$id/$action')).timeout(AppConfig.requestTimeout);
    if (response.statusCode == 200) return Citizen.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
    throw Exception(_callError(response, 'Record could not be $action'));
  }

  @override
  Future<Citizen> archiveCitizen(String id) => _archiveAction(id, 'archive');

  @override
  Future<Citizen> restoreCitizen(String id) => _archiveAction(id, 'restore');

  @override
  Future<Map<String, dynamic>> importRecords(String path) async {
    final uri = _uri('citizens/import');
    final request = http.MultipartRequest('POST', uri)..files.add(await http.MultipartFile.fromPath('file', path));
    final streamed = await _client.send(request).timeout(AppConfig.requestTimeout);
    final response = await http.Response.fromStream(streamed);
    final data = jsonDecode(response.body);
    if (response.statusCode == 200) return data as Map<String, dynamic>;
    throw Exception(_callError(response, 'Import failed'));
  }

  @override
  Future<String> exportRecords(String format) async {
    final response = await _client.get(_uri('citizens/export', {'format': format})).timeout(AppConfig.requestTimeout);
    if (response.statusCode == 200) return response.body;
    throw Exception(_callError(response, 'Export failed'));
  }

  @override
  Future<CitizenDobUpdateResult> updateCitizenDob(
    String citizenId,
    DateTime newDob,
  ) async {
    final formattedDob =
        '${newDob.year.toString().padLeft(4, '0')}-${newDob.month.toString().padLeft(2, '0')}-${newDob.day.toString().padLeft(2, '0')}';

    final response = await _client
        .patch(
          _uri('citizens/$citizenId'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'date_of_birth': formattedDob}),
        )
        .timeout(AppConfig.requestTimeout);

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      final updatedCitizen = await getCitizenById(citizenId);
      final event = data['event_detected'] as String?;
      return CitizenDobUpdateResult(
        citizen: updatedCitizen,
        previousAge: (data['previous_age'] as num?)?.toInt() ?? 0,
        newAge: (data['calculated_age'] as num?)?.toInt() ?? updatedCitizen.age,
        eventDetected: event,
      );
    } else {
      throw Exception('Failed to update DOB: HTTP ${response.statusCode}');
    }
  }

  @override
  Future<List<EligibilityResult>> getEligibility(String citizenId) async {
    return evaluateEligibility(citizenId);
  }

  @override
  Future<List<EligibilityResult>> evaluateEligibility(String citizenId) async {
    final response = await _client
        .post(
          _uri('citizens/$citizenId/evaluate'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({}),
        )
        .timeout(AppConfig.requestTimeout);

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      final list = (data['eligible_services'] as List<dynamic>?) ?? [];
      return list.map((e) {
        return EligibilityResult(
          id: 'elg-$citizenId-${e['service_code']}',
          citizenId: citizenId,
          service: ServiceScheme.fromJson(e as Map<String, dynamic>),
          isEligible: true,
          evaluatedAt: DateTime.now(),
          qualificationReason: 'Evaluated as qualified by backend rule engine.',
        );
      }).toList();
    } else {
      throw Exception('Evaluation failed: HTTP ${response.statusCode}');
    }
  }

  @override
  Future<List<CallJob>> getCallJobs({String? citizenId}) async {
    final params = citizenId != null ? {'citizen_id': citizenId} : null;
    final response = await _client
        .get(_uri('demo/calls', params))
        .timeout(AppConfig.requestTimeout);

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      final list = (data is Map && data.containsKey('jobs'))
          ? data['jobs'] as List<dynamic>
          : data as List<dynamic>;
      return list
          .map((e) => CallJob.fromJson(e as Map<String, dynamic>))
          .toList();
    } else {
      throw Exception('Failed to fetch call jobs: HTTP ${response.statusCode}');
    }
  }

  @override
  Future<CallJob> scheduleCallJob(String citizenId, String triggerEvent) async {
    final response = await _client
        .post(
          _uri('demo/calls'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'citizen_id': citizenId,
            'trigger_event': triggerEvent,
          }),
        )
        .timeout(AppConfig.requestTimeout);

    if (response.statusCode == 201 || response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      return CallJob.fromJson(data);
    } else if (response.statusCode == 409) {
      throw Exception(
        'Duplicate call job already exists (Idempotency Enforced).',
      );
    } else {
      throw Exception('Call dispatch failed: HTTP ${response.statusCode}');
    }
  }

  @override
  Future<CallJob> createDryRunCall({
    required String citizenId,
    required String testRecipientNumber,
  }) async {
    final response = await _client
        .post(
          _uri('demo/calls/dry-run'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'citizen_id': citizenId,
            'trigger_event':
                'MANUAL_DRY_RUN_${DateTime.now().millisecondsSinceEpoch}',
            'test_recipient_number': testRecipientNumber,
            'recipient_has_consented': true,
          }),
        )
        .timeout(AppConfig.requestTimeout);
    if (response.statusCode == 201) {
      return CallJob.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>,
      );
    }
    throw Exception(
      _callError(response, 'Dry-run rehearsal could not be created'),
    );
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
    final response = await _client
        .post(
          _uri('calls/approved-test'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'citizen_id': citizenId,
            'test_recipient_number': testRecipientNumber,
            'language': language,
            'recipient_has_consented': recipientHasConsented,
            'script_reviewed': scriptReviewed,
            'ai_disclosure_confirmed': aiDisclosureConfirmed,
            'caller_id_reviewed': callerIdReviewed,
            'confirm_single_call': confirmSingleCall,
            'confirmation_phrase': confirmationPhrase,
          }),
        )
        .timeout(AppConfig.callRequestTimeout);
    if (response.statusCode == 201) {
      return CallJob.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>,
      );
    }
    throw Exception(
      _callError(response, 'Approved test call was not accepted'),
    );
  }

  @override
  Future<CallJob> refreshCallJobStatus(String callId) async {
    final response = await _client
        .post(_uri('calls/$callId/refresh-status'))
        .timeout(AppConfig.callRequestTimeout);
    if (response.statusCode == 200) {
      return CallJob.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>,
      );
    }
    throw Exception(_callError(response, 'Call status could not be refreshed'));
  }

  @override
  Future<CallJob> stopQueuedCall(String callId) async {
    final response = await _client
        .post(_uri('calls/$callId/stop'))
        .timeout(AppConfig.callRequestTimeout);
    if (response.statusCode == 200) {
      return CallJob.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>,
      );
    }
    throw Exception(_callError(response, 'Pending call could not be canceled'));
  }

  @override
  Future<List<ServiceScheme>> getServices() async {
    final response = await _client
        .get(_uri('services'))
        .timeout(AppConfig.requestTimeout);

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as List<dynamic>;
      return data
          .map((e) => ServiceScheme.fromJson(e as Map<String, dynamic>))
          .toList();
    } else {
      throw Exception('Failed to load services: HTTP ${response.statusCode}');
    }
  }
}
