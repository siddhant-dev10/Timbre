import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../models/call_job.dart';
import '../../models/call_event.dart';
import '../../state/app_state.dart';

class CallMonitorScreen extends StatefulWidget {
  final AppState state;

  const CallMonitorScreen({super.key, required this.state});

  @override
  State<CallMonitorScreen> createState() => _CallMonitorScreenState();
}

class _CallMonitorScreenState extends State<CallMonitorScreen> {
  CallJob? _selectedJob;

  @override
  Widget build(BuildContext context) {
    final state = widget.state;
    final callJobs = state.callJobs;

    if (_selectedJob == null && callJobs.isNotEmpty) {
      _selectedJob = callJobs.first;
    }

    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Simulated Outbound Call Monitor',
                    style: TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                      color: AppTheme.textPrimaryLight,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Queue of idempotent call jobs and real-time conversational Hinglish transcripts',
                    style: const TextStyle(
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
          const SizedBox(height: 20),

          // Main split view: Job Queue on Left, Transcript on Right
          Expanded(
            child: callJobs.isEmpty
                ? const Center(
                    child: Text(
                      'No simulated call jobs in the queue yet.\nUse Life-Event Simulation to generate a milestone call.',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: AppTheme.textSecondaryLight),
                    ),
                  )
                : Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Left: Jobs list
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
                                  backgroundColor: job.isCompleted
                                      ? AppTheme.statusGreen.withValues(
                                          alpha: 0.15,
                                        )
                                      : AppTheme.accentSaffron.withValues(
                                          alpha: 0.2,
                                        ),
                                  child: Icon(
                                    job.isCompleted
                                        ? Icons.check
                                        : Icons.access_time,
                                    size: 16,
                                    color: job.isCompleted
                                        ? AppTheme.statusGreen
                                        : AppTheme.warningAmber,
                                  ),
                                ),
                                title: Row(
                                  mainAxisAlignment:
                                      MainAxisAlignment.spaceBetween,
                                  children: [
                                    Text(
                                      job.citizenName,
                                      style: const TextStyle(
                                        fontWeight: FontWeight.bold,
                                        fontSize: 13,
                                      ),
                                    ),
                                    Container(
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 6,
                                        vertical: 2,
                                      ),
                                      decoration: BoxDecoration(
                                        color: job.isCompleted
                                            ? AppTheme.statusGreen.withValues(
                                                alpha: 0.12,
                                              )
                                            : AppTheme.accentSaffron.withValues(
                                                alpha: 0.2,
                                              ),
                                        borderRadius: BorderRadius.circular(4),
                                      ),
                                      child: Text(
                                        job.jobStatus,
                                        style: TextStyle(
                                          fontSize: 10,
                                          fontWeight: FontWeight.bold,
                                          color: job.isCompleted
                                              ? AppTheme.statusGreen
                                              : AppTheme.warningAmber,
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                                subtitle: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      'Trigger: ${job.triggerEvent}',
                                      style: const TextStyle(fontSize: 12),
                                    ),
                                    Text(
                                      'Key: ${job.idempotencyKey}',
                                      style: const TextStyle(
                                        fontSize: 10,
                                        fontFamily: 'monospace',
                                        color: AppTheme.textSecondaryLight,
                                      ),
                                    ),
                                  ],
                                ),
                                onTap: () {
                                  setState(() {
                                    _selectedJob = job;
                                  });
                                },
                              );
                            },
                          ),
                        ),
                      ),
                      const SizedBox(width: 20),

                      // Right: Transcript Inspector
                      Expanded(
                        flex: 6,
                        child: _selectedJob == null
                            ? const Card(
                                child: Center(
                                  child: Text(
                                    'Select a job to view transcript',
                                  ),
                                ),
                              )
                            : _buildTranscriptPanel(_selectedJob!),
                      ),
                    ],
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildTranscriptPanel(CallJob job) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Transcript: ${job.citizenName}',
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    Text(
                      'Job ID: ${job.id} • Trigger: ${job.triggerEvent}',
                      style: const TextStyle(
                        fontSize: 11,
                        color: AppTheme.textSecondaryLight,
                      ),
                    ),
                  ],
                ),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 4,
                  ),
                  decoration: BoxDecoration(
                    color: AppTheme.primaryNavy.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    'Duration: ${job.durationSeconds}s',
                    style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                      color: AppTheme.primaryNavy,
                    ),
                  ),
                ),
              ],
            ),
            const Divider(height: 24),

            if (job.transcriptEvents.isEmpty)
              Expanded(
                child: Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(
                        Icons.hourglass_empty,
                        size: 36,
                        color: Colors.grey,
                      ),
                      const SizedBox(height: 12),
                      Text(
                        'Call is currently ${job.jobStatus}.\nTranscript will appear once audio stream is processed.',
                        textAlign: TextAlign.center,
                        style: const TextStyle(
                          fontSize: 13,
                          color: AppTheme.textSecondaryLight,
                        ),
                      ),
                    ],
                  ),
                ),
              )
            else
              Expanded(
                child: ListView.separated(
                  itemCount: job.transcriptEvents.length,
                  separatorBuilder: (context, index) =>
                      const SizedBox(height: 12),
                  itemBuilder: (context, index) {
                    final event = job.transcriptEvents[index];
                    return _buildSpeechBubble(event);
                  },
                ),
              ),
          ],
        ),
      ),
    );
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
                  color: isAi ? AppTheme.primaryNavy : Colors.blue.shade800,
                ),
                const SizedBox(width: 4),
                Text(
                  isAi ? 'Timbre Assistant (AI)' : 'Citizen',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                    color: isAi ? AppTheme.primaryNavy : Colors.blue.shade800,
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
}
