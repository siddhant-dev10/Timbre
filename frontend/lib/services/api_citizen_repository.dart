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

/// Real REST API client communicating with the ASUS FastAPI backend.
class ApiCitizenRepository implements CitizenRepository {
  final http.Client _client;

  ApiCitizenRepository({http.Client? client})
    : _client = client ?? http.Client();

  @override
  bool get isMock => false;

  @override
  String get dataSourceDescription =>
      'ASUS FastAPI Backend (${AppConfig.backendUrl})';

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
        return BackendHealth.connected(
          AppConfig.backendUrl,
          stopwatch.elapsedMilliseconds,
          version,
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
    int limit = 20,
    int offset = 0,
    String? query,
  }) async {
    final params = <String, dynamic>{'limit': limit, 'offset': offset};
    if (query != null && query.isNotEmpty) {
      params['q'] = query;
    }

    final response = await _client
        .get(_uri('citizens', params))
        .timeout(AppConfig.requestTimeout);

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
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
