import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:timbre/core/config/app_config.dart';
import 'package:timbre/services/api_citizen_repository.dart';

Map<String, dynamic> _callResponse({
  String status = 'QUEUED',
  bool real = false,
  String recipient = '***0099',
  String? executionId,
}) => {
  'id': 'call-id',
  'citizen_id': 'CIT-0009',
  'citizen_name': real ? 'Consenting test recipient' : 'Synthetic test profile',
  'trigger_event': real ? 'MANUAL_APPROVED_TEST' : 'MANUAL_DRY_RUN',
  'job_status': status,
  'idempotency_key': 'test-key',
  'attempt_count': 1,
  'scheduled_at': DateTime.utc(2026, 10, 29).toIso8601String(),
  'duration_seconds': 0,
  'is_real_call': real,
  'recipient_phone': recipient,
  'bolna_execution_id': executionId,
  'transcript_events': <dynamic>[],
};

void main() {
  const previousUrl = AppConfig.defaultBackendUrl;

  setUp(() {
    AppConfig.backendUrl = 'http://127.0.0.1:8000/api/v1';
  });

  tearDown(() {
    AppConfig.backendUrl = previousUrl;
  });

  test(
    'dry-run sends the recipient only to the local dry-run endpoint',
    () async {
      late http.Request captured;
      final client = MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode(_callResponse(status: 'COMPLETED')),
          201,
          headers: {'content-type': 'application/json'},
        );
      });
      addTearDown(client.close);
      final repository = ApiCitizenRepository(client: client);

      final result = await repository.createDryRunCall(
        citizenId: 'CIT-0009',
        testRecipientNumber: '9000000099',
      );

      expect(captured.method, 'POST');
      expect(captured.url.path, '/api/v1/demo/calls/dry-run');
      final body = jsonDecode(captured.body) as Map<String, dynamic>;
      expect(body['test_recipient_number'], '9000000099');
      expect(body['recipient_has_consented'], isTrue);
      expect(result.isRealCall, isFalse);
      expect(result.recipientPhone, '***0099');
    },
  );

  test(
    'approved test-call API requires an explicit one-call review payload',
    () async {
      late http.Request captured;
      final client = MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode(_callResponse(real: true, executionId: 'execution-id')),
          201,
          headers: {'content-type': 'application/json'},
        );
      });
      addTearDown(client.close);
      final repository = ApiCitizenRepository(client: client);

      final result = await repository.createApprovedTestCall(
        citizenId: 'CIT-0009',
        testRecipientNumber: '9000000099',
        language: 'hi',
        recipientHasConsented: true,
        scriptReviewed: true,
        aiDisclosureConfirmed: true,
        callerIdReviewed: true,
        confirmSingleCall: true,
        confirmationPhrase: 'CALL ONCE',
      );

      expect(captured.url.path, '/api/v1/calls/approved-test');
      final body = jsonDecode(captured.body) as Map<String, dynamic>;
      expect(body['language'], 'hi');
      expect(body['recipient_has_consented'], isTrue);
      expect(body['script_reviewed'], isTrue);
      expect(body['ai_disclosure_confirmed'], isTrue);
      expect(body['caller_id_reviewed'], isTrue);
      expect(body['confirm_single_call'], isTrue);
      expect(body['confirmation_phrase'], 'CALL ONCE');
      expect(result.isRealCall, isTrue);
      expect(result.bolnaExecutionId, 'execution-id');
      expect(result.recipientPhone, '***0099');
    },
  );
}
