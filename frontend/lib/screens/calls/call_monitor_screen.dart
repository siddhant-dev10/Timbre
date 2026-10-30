import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../models/call_event.dart';
import '../../models/call_job.dart';
import '../../models/citizen.dart';
import '../../state/app_state.dart';

class CallMonitorScreen extends StatefulWidget {
  final AppState state;

  const CallMonitorScreen({super.key, required this.state});

  @override
  State<CallMonitorScreen> createState() => _CallMonitorScreenState();
}

class _CallMonitorScreenState extends State<CallMonitorScreen> {
  CallJob? _selectedJob;
  final _numberController = TextEditingController();
  final _confirmationController = TextEditingController();
  bool _liveMode = false;
  bool _recipientConsented = false;
  bool _scriptReviewed = false;
  bool _aiDisclosureConfirmed = false;
  bool _callerIdReviewed = false;
  bool _busy = false;
  String _language = 'hi';

  static const _openingDisclosure =
      'Namaste, main Timbre hoon, ek AI assistant. Yeh ek approved test call hai. Main sirf fictional demo jaankari use karungi.';
  static const _testScript =
      'Use a fictional adult profile in Rajasthan asking how to check a government-service eligibility rule. Do not claim eligibility or invent current requirements; direct the caller to the relevant official government source.';

  @override
  void dispose() {
    _numberController.dispose();
    _confirmationController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = widget.state;
    final callJobs = state.callJobs;
    if (_selectedJob == null && callJobs.isNotEmpty) {
      _selectedJob = callJobs.first;
    } else if (_selectedJob != null) {
      final refreshed = callJobs.where((job) => job.id == _selectedJob!.id);
      if (refreshed.isNotEmpty) _selectedJob = refreshed.first;
    }

    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Call tests and status',
                    style: TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                      color: AppTheme.textPrimaryLight,
                    ),
                  ),
                  SizedBox(height: 4),
                  Text(
                    'Review a local simulation or authorize one test call.',
                    style: TextStyle(
                      fontSize: 13,
                      color: AppTheme.textSecondaryLight,
                    ),
                  ),
                ],
              ),
              IconButton.outlined(
                tooltip: 'Refresh Queue',
                onPressed: () => state.loadCallJobs(),
                icon: const Icon(Icons.refresh, size: 20),
              ),
            ],
          ),
          const SizedBox(height: 14),
          _buildTestCallCard(state),
          if (state.callsError != null) ...[
            const SizedBox(height: 8),
            Text(
              state.callsError!,
              style: const TextStyle(color: AppTheme.errorRed, fontSize: 12),
            ),
          ],
          const SizedBox(height: 14),
          Expanded(
            child: callJobs.isEmpty
                ? const Center(
                    child: Text(
                      'No test call history yet. Run a local dry-run above to create a review transcript.',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: AppTheme.textSecondaryLight),
                    ),
                  )
                : Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        flex: 5,
                        child: Card(
                          clipBehavior: Clip.antiAlias,
                          child: ListView.separated(
                            itemCount: callJobs.length,
                            separatorBuilder: (context, index) =>
                                const Divider(height: 1),
                            itemBuilder: (context, index) {
                              final job = callJobs[index];
                              final isSelected = _selectedJob?.id == job.id;
                              return ListTile(
                                selected: isSelected,
                                selectedTileColor: AppTheme.primaryNavy
                                    .withValues(alpha: 0.06),
                                leading: CircleAvatar(
                                  radius: 16,
                                  backgroundColor: _statusColor(job.jobStatus)
                                      .withValues(alpha: 0.15),
                                  child: Icon(
                                    _statusIcon(job.jobStatus),
                                    size: 16,
                                    color: _statusColor(job.jobStatus),
                                  ),
                                ),
                                title: Row(
                                  mainAxisAlignment:
                                      MainAxisAlignment.spaceBetween,
                                  children: [
                                    Flexible(
                                      child: Text(
                                        job.isRealCall
                                            ? 'Approved test call'
                                            : job.citizenName,
                                        overflow: TextOverflow.ellipsis,
                                        style: const TextStyle(
                                          fontWeight: FontWeight.bold,
                                          fontSize: 13,
                                        ),
                                      ),
                                    ),
                                    const SizedBox(width: 6),
                                    _statusChip(job.jobStatus),
                                  ],
                                ),
                                subtitle: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      '${job.isRealCall ? 'Live test' : 'Simulation'} • ${job.triggerEvent}',
                                      style: const TextStyle(fontSize: 11),
                                    ),
                                    if (job.recipientPhone != '***')
                                      Text(
                                        'Recipient: ${job.recipientPhone}',
                                        style: const TextStyle(fontSize: 11),
                                      ),
                                  ],
                                ),
                                onTap: () => setState(() => _selectedJob = job),
                              );
                            },
                          ),
                        ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        flex: 6,
                        child: _selectedJob == null
                            ? const Card(
                                child: Center(child: Text('Select a job')),
                              )
                            : _buildTranscriptPanel(state, _selectedJob!),
                      ),
                    ],
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildTestCallCard(AppState state) {
    final selectedCitizen =
        state.selectedCitizen ??
        (state.citizens.isEmpty ? null : state.citizens.first);
    final liveReady =
        !state.isDemoMode &&
        state.backendHealth.isConnected &&
        state.backendHealth.bolnaTestCallReady;
    final canSubmit =
        !_busy &&
        selectedCitizen != null &&
        _recipientConsented &&
        _numberController.text.trim().isNotEmpty &&
        (!_liveMode ||
            (liveReady &&
                _scriptReviewed &&
                _aiDisclosureConfirmed &&
                _callerIdReviewed &&
                _confirmationController.text.trim() == 'CALL ONCE'));

    return Card(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxHeight: 420),
        child: SingleChildScrollView(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(
                      Icons.phone_in_talk_outlined,
                      color: AppTheme.primaryNavy,
                    ),
                    const SizedBox(width: 8),
                    const Expanded(
                      child: Text(
                        'One-recipient test',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                    ChoiceChip(
                      label: const Text('Local dry-run'),
                      selected: !_liveMode,
                      onSelected: (selected) {
                        if (selected) {
                          setState(() {
                            _liveMode = false;
                            _recipientConsented = false;
                            _scriptReviewed = false;
                            _aiDisclosureConfirmed = false;
                            _callerIdReviewed = false;
                            _confirmationController.clear();
                          });
                        }
                      },
                    ),
                    const SizedBox(width: 8),
                    ChoiceChip(
                      label: const Text('Approved live test'),
                      selected: _liveMode,
                      onSelected: (selected) {
                        if (selected) {
                          setState(() {
                            _liveMode = true;
                            _recipientConsented = false;
                            _scriptReviewed = false;
                            _aiDisclosureConfirmed = false;
                            _callerIdReviewed = false;
                            _confirmationController.clear();
                          });
                        }
                      },
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      flex: 3,
                      child: TextField(
                        controller: _numberController,
                        keyboardType: TextInputType.phone,
                        onChanged: (_) {
                          setState(() {
                            _recipientConsented = false;
                            _scriptReviewed = false;
                            _aiDisclosureConfirmed = false;
                            _callerIdReviewed = false;
                            _confirmationController.clear();
                          });
                        },
                        decoration: const InputDecoration(
                          labelText: 'Test recipient phone number',
                          hintText: 'Indian 10-digit or international +E.164',
                          prefixIcon: Icon(Icons.phone_outlined),
                          isDense: true,
                        ),
                      ),
                    ),
                    if (_liveMode) ...[
                      const SizedBox(width: 12),
                      Expanded(
                        child: DropdownButtonFormField<String>(
                          isExpanded: true,
                          initialValue: _language,
                          decoration: const InputDecoration(
                            labelText: 'Starting language',
                            isDense: true,
                          ),
                          items: const [
                            DropdownMenuItem(
                              value: 'hi',
                              child: Text(
                                'Hindi / Hinglish',
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                            DropdownMenuItem(
                              value: 'en',
                              child: Text('English'),
                            ),
                          ],
                          onChanged: (value) =>
                              setState(() => _language = value ?? 'hi'),
                        ),
                      ),
                    ],
                  ],
                ),
                CheckboxListTile(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  controlAffinity: ListTileControlAffinity.leading,
                  title: const Text(
                    'The recipient agreed to receive this one test call.',
                  ),
                  value: _recipientConsented,
                  onChanged: (value) =>
                      setState(() => _recipientConsented = value ?? false),
                ),
                if (_liveMode) ...[
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: AppTheme.warningAmber.withValues(alpha: 0.10),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Text(
                      'A live call can incur Bolna, telephony, NVIDIA and speech-provider charges. The caller ID comes from the configured provider; Timbre does not use or verify a personal number.',
                      style: TextStyle(fontSize: 12, height: 1.35),
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    'Opening line: “$_openingDisclosure”',
                    style: const TextStyle(fontSize: 11),
                  ),
                  Text(
                    'Test scenario: $_testScript',
                    style: const TextStyle(fontSize: 11),
                  ),
                  CheckboxListTile(
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                    controlAffinity: ListTileControlAffinity.leading,
                    title: const Text(
                      'I reviewed the exact fictional test script above.',
                    ),
                    value: _scriptReviewed,
                    onChanged: (value) =>
                        setState(() => _scriptReviewed = value ?? false),
                  ),
                  CheckboxListTile(
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                    controlAffinity: ListTileControlAffinity.leading,
                    title: const Text(
                      'The configured agent starts by identifying itself as an AI assistant.',
                    ),
                    value: _aiDisclosureConfirmed,
                    onChanged: (value) =>
                        setState(() => _aiDisclosureConfirmed = value ?? false),
                  ),
                  const Padding(
                    padding: EdgeInsets.only(left: 12, right: 12, bottom: 4),
                    child: Text(
                      'Timbre uses the Bolna account default caller ID. Check the active outbound number in Bolna and confirm it is authorized for this test. Do not proceed if it is unknown or unverified.',
                      style: TextStyle(
                        fontSize: 11,
                        color: AppTheme.textSecondaryLight,
                      ),
                    ),
                  ),
                  CheckboxListTile(
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                    controlAffinity: ListTileControlAffinity.leading,
                    title: const Text(
                      'I verified and approved the configured Bolna caller ID for this test.',
                    ),
                    value: _callerIdReviewed,
                    onChanged: (value) =>
                        setState(() => _callerIdReviewed = value ?? false),
                  ),
                  SizedBox(
                    width: 220,
                    child: TextField(
                      controller: _confirmationController,
                      onChanged: (_) => setState(() {}),
                      decoration: const InputDecoration(
                        labelText: 'Type CALL ONCE',
                        isDense: true,
                      ),
                    ),
                  ),
                  const SizedBox(height: 5),
                  Text(
                    state.isDemoMode
                        ? 'Switch to the Mac backend to use call controls.'
                        : !state.backendHealth.isConnected
                        ? 'Connect the Mac backend before placing a call.'
                        : !state.backendHealth.bolnaTestCallReady
                        ? 'Live calls are locked. Configure Bolna, verify the test agent, then enable live calls locally.'
                        : 'Only one call is submitted. Automatic retries are disabled.',
                    style: const TextStyle(
                      fontSize: 11,
                      color: AppTheme.textSecondaryLight,
                    ),
                  ),
                ] else
                  const Padding(
                    padding: EdgeInsets.only(bottom: 8),
                    child: Text(
                      'Dry-run stores a short fictional transcript locally. The phone number is validated, masked, and never sent to a phone provider.',
                      style: TextStyle(
                        fontSize: 11,
                        color: AppTheme.textSecondaryLight,
                      ),
                    ),
                  ),
                Align(
                  alignment: Alignment.centerRight,
                  child: FilledButton.icon(
                    onPressed: canSubmit
                        ? () => _liveMode
                              ? _confirmAndPlaceCall(state, selectedCitizen)
                              : _runDryRun(state, selectedCitizen)
                        : null,
                    icon: Icon(
                      _liveMode
                          ? Icons.phone_forwarded
                          : Icons.science_outlined,
                    ),
                    label: Text(
                      _busy
                          ? 'Submitting…'
                          : _liveMode
                          ? 'Review and place one call'
                          : 'Run local dry-run',
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _runDryRun(AppState state, Citizen citizen) async {
    setState(() => _busy = true);
    try {
      final job = await state.createDryRunCall(
        citizenId: citizen.id,
        testRecipientNumber: _numberController.text.trim(),
      );
      if (!mounted) return;
      setState(() {
        _selectedJob = job;
        _numberController.clear();
        _recipientConsented = false;
      });
      _showMessage('Local dry-run created. No call was placed.');
    } catch (error) {
      if (mounted) _showMessage(_cleanError(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _confirmAndPlaceCall(AppState state, Citizen citizen) async {
    final enteredNumber = _numberController.text.trim();
    final digits = enteredNumber.replaceAll(RegExp(r'\D'), '');
    final masked = digits.length >= 4
        ? '***${digits.substring(digits.length - 4)}'
        : '***';
    final approved = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Place this one test call?'),
        content: SizedBox(
          width: 520,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Recipient: $masked'),
              const SizedBox(height: 8),
              const Text(
                'Timbre will identify itself as an AI assistant and use only the fictional scenario shown on the Calls screen.',
              ),
              const SizedBox(height: 8),
              const Text(
                'The call provider may charge for telephony and AI services. The request will not be retried automatically.',
              ),
              const SizedBox(height: 8),
              const Text(
                'The call will use Bolna’s account default caller ID. You confirmed that you checked and approved it for this test.',
              ),
              const SizedBox(height: 8),
              const Text(
                'If it is already active, this app cannot hang it up through Bolna’s documented API. The recipient will need to end the call from their phone.',
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Place this call now'),
          ),
        ],
      ),
    );
    if (approved != true || !mounted) return;

    setState(() => _busy = true);
    try {
      final job = await state.createApprovedTestCall(
        citizenId: citizen.id,
        testRecipientNumber: enteredNumber,
        language: _language,
        recipientHasConsented: _recipientConsented,
        scriptReviewed: _scriptReviewed,
        aiDisclosureConfirmed: _aiDisclosureConfirmed,
        callerIdReviewed: _callerIdReviewed,
        confirmSingleCall: approved == true,
        confirmationPhrase: _confirmationController.text.trim(),
      );
      if (!mounted) return;
      setState(() {
        _selectedJob = job;
        _numberController.clear();
        _confirmationController.clear();
        _recipientConsented = false;
        _scriptReviewed = false;
        _aiDisclosureConfirmed = false;
        _callerIdReviewed = false;
      });
      _showMessage(
        'One call was submitted. Refresh its status; do not retry if the result is unknown.',
      );
    } catch (error) {
      if (mounted) _showMessage(_cleanError(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Widget _buildTranscriptPanel(AppState state, CallJob job) {
    final canCancelPending =
        job.isRealCall &&
        job.bolnaExecutionId != null &&
        (job.jobStatus == 'QUEUED' || job.jobStatus == 'SCHEDULED');
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        job.isRealCall
                            ? 'Approved test call'
                            : 'Local simulation',
                        style: const TextStyle(
                          fontSize: 17,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      Text(
                        'Status: ${job.jobStatus} • Recipient: ${job.recipientPhone}',
                        style: const TextStyle(
                          fontSize: 11,
                          color: AppTheme.textSecondaryLight,
                        ),
                      ),
                    ],
                  ),
                ),
                if (job.isRealCall)
                  IconButton(
                    tooltip: 'Refresh provider status',
                    onPressed: _busy ? null : () => _refreshStatus(state, job),
                    icon: const Icon(Icons.sync),
                  ),
                if (canCancelPending)
                  IconButton(
                    tooltip: 'Cancel pending call',
                    onPressed: _busy ? null : () => _cancelPending(state, job),
                    icon: const Icon(Icons.call_end, color: AppTheme.errorRed),
                  ),
              ],
            ),
            const Divider(height: 20),
            if (job.isRealCall)
              const Padding(
                padding: EdgeInsets.only(bottom: 10),
                child: Text(
                  'Timbre stores only the masked recipient, call status, duration and provider execution ID. It does not copy provider transcripts or recordings into the local database.',
                  style: TextStyle(
                    fontSize: 11,
                    color: AppTheme.textSecondaryLight,
                  ),
                ),
              ),
            if (job.transcriptEvents.isEmpty)
              const Expanded(
                child: Center(
                  child: Text(
                    'No transcript is stored for this job. Refresh the provider status for progress.',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 13,
                      color: AppTheme.textSecondaryLight,
                    ),
                  ),
                ),
              )
            else
              Expanded(
                child: ListView.separated(
                  itemCount: job.transcriptEvents.length,
                  separatorBuilder: (context, index) =>
                      const SizedBox(height: 12),
                  itemBuilder: (context, index) =>
                      _buildSpeechBubble(job.transcriptEvents[index]),
                ),
              ),
            if (job.isRealCall &&
                (job.jobStatus == 'IN_PROGRESS' ||
                    job.jobStatus == 'FINALIZING'))
              const Text(
                'This call may be active. Bolna’s documented stop endpoint only cancels queued or scheduled calls; end an active call from the recipient phone.',
                style: TextStyle(fontSize: 11, color: AppTheme.warningAmber),
              ),
          ],
        ),
      ),
    );
  }

  Future<void> _refreshStatus(AppState state, CallJob job) async {
    setState(() => _busy = true);
    try {
      final refreshed = await state.refreshCallJobStatus(job.id);
      if (mounted) setState(() => _selectedJob = refreshed);
    } catch (error) {
      if (mounted) _showMessage(_cleanError(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _cancelPending(AppState state, CallJob job) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Cancel this pending call?'),
        content: const Text(
          'Bolna can cancel this call only while it is queued or scheduled.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Keep call'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Cancel pending call'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    setState(() => _busy = true);
    try {
      final stopped = await state.stopQueuedCall(job.id);
      if (mounted) setState(() => _selectedJob = stopped);
    } catch (error) {
      if (mounted) _showMessage(_cleanError(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Widget _buildSpeechBubble(CallEvent event) {
    final isAi = event.isAi;
    return Align(
      alignment: isAi ? Alignment.centerLeft : Alignment.centerRight,
      child: Container(
        constraints: const BoxConstraints(maxWidth: 420),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: isAi
              ? AppTheme.primaryNavy.withValues(alpha: 0.08)
              : Colors.blue.shade50,
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(12),
            topRight: const Radius.circular(12),
            bottomLeft: Radius.circular(isAi ? 0 : 12),
            bottomRight: Radius.circular(isAi ? 12 : 0),
          ),
          border: Border.all(
            color: isAi
                ? AppTheme.primaryNavy.withValues(alpha: 0.2)
                : Colors.blue.shade200,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  isAi ? Icons.smart_toy_outlined : Icons.person_outline,
                  size: 14,
                ),
                const SizedBox(width: 4),
                Text(
                  isAi ? 'Timbre Assistant (AI)' : 'Test recipient',
                  style: const TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                if (event.latencyMs > 0) ...[
                  const SizedBox(width: 8),
                  Text(
                    '${event.latencyMs}ms',
                    style: TextStyle(fontSize: 10, color: Colors.grey.shade600),
                  ),
                ],
              ],
            ),
            const SizedBox(height: 4),
            Text(
              event.transcriptSegment,
              style: const TextStyle(fontSize: 13, height: 1.4),
            ),
          ],
        ),
      ),
    );
  }

  Widget _statusChip(String status) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
    decoration: BoxDecoration(
      color: _statusColor(status).withValues(alpha: 0.12),
      borderRadius: BorderRadius.circular(4),
    ),
    child: Text(
      status,
      style: TextStyle(
        fontSize: 10,
        fontWeight: FontWeight.bold,
        color: _statusColor(status),
      ),
    ),
  );

  Color _statusColor(String status) {
    if (status == 'COMPLETED' || status == 'STOPPED') {
      return AppTheme.statusGreen;
    }
    if (status == 'FAILED' || status == 'UNKNOWN') {
      return AppTheme.errorRed;
    }
    if (status == 'IN_PROGRESS' || status == 'FINALIZING') {
      return AppTheme.primaryNavy;
    }
    return AppTheme.warningAmber;
  }

  IconData _statusIcon(String status) {
    if (status == 'COMPLETED' || status == 'STOPPED') {
      return Icons.check;
    }
    if (status == 'FAILED' || status == 'UNKNOWN') {
      return Icons.error_outline;
    }
    if (status == 'IN_PROGRESS' || status == 'FINALIZING') {
      return Icons.phone_in_talk;
    }
    return Icons.access_time;
  }

  String _cleanError(Object error) =>
      error.toString().replaceFirst(RegExp(r'^Exception:\s*'), '');

  void _showMessage(String message) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }
}
