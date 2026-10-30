import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../state/app_state.dart';

class DashboardScreen extends StatelessWidget {
  final AppState state;
  final ValueChanged<int> onNavigate;

  const DashboardScreen({
    super.key,
    required this.state,
    required this.onNavigate,
  });

  @override
  Widget build(BuildContext context) {
    final citizens = state.citizens;
    final callJobs = state.callJobs;
    final totalCitizens = state.citizensTotal;
    final syntheticRecords = citizens.where((c) => c.isFictional).length;
    final validRecords = citizens.where((c) => c.fullName.trim().isNotEmpty && c.state.trim().isNotEmpty && c.district.trim().isNotEmpty && c.cityOrVillage.trim().isNotEmpty).length;
    final needsReview = totalCitizens - validRecords;
    final turning18Candidates = citizens.where((c) => c.age == 17).length;
    final adults = citizens.where((c) => c.isAdult).length;
    final completedCalls = callJobs.where((j) => j.isCompleted).length;
    final queuedCalls = callJobs.where((j) => j.isQueued).length;
    final failedCalls = callJobs.where((j) => j.isFailed).length;
    final awaitingReview = callJobs.where((j) => const {'SUBMITTING', 'UNKNOWN', 'NEEDS_REVIEW'}.contains(j.jobStatus)).length;
    final simulatedCalls = callJobs.where((j) => !j.isRealCall).length;
    final milestoneCandidate = citizens.where((c) => c.isFictional && c.age == 17).firstOrNull ?? citizens.where((c) => c.isFictional).firstOrNull;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Administrative Overview',
                      style: TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.textPrimaryLight,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Proactive government scheme detection & simulated outreach cockpit',
                      style: TextStyle(
                        fontSize: 14,
                        color: AppTheme.textSecondaryLight,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 16),
              FilledButton.icon(
                onPressed: () =>
                    onNavigate(2), // Navigate to Life-Event Simulation
                icon: const Icon(Icons.bolt, size: 18),
                label: const Text('Simulate Life Event'),
                style: FilledButton.styleFrom(
                  backgroundColor: AppTheme.accentSaffron,
                  foregroundColor: Colors.black87,
                  padding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 12,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 24),

          // Metric Cards Grid
          LayoutBuilder(
            builder: (context, constraints) {
              final isWide = constraints.maxWidth > 800;
              final cardWidth = isWide
                  ? (constraints.maxWidth - 48) / 4
                  : (constraints.maxWidth - 16) / 2;

              return Wrap(
                spacing: 16,
                runSpacing: 16,
                children: [
                  _buildMetricCard(
                    title: 'Total Records',
                    value: '$totalCitizens',
                    subtitle:
                        '$syntheticRecords synthetic on this page; $adults adults, $turning18Candidates age 17',
                    icon: Icons.people_alt_outlined,
                    color: AppTheme.primaryNavy,
                    onTap: () => onNavigate(1),
                    width: cardWidth,
                  ),
                  _buildMetricCard(
                    title: 'Milestone Candidates',
                    value: '$turning18Candidates',
                    subtitle: 'Citizens aged 17 nearing Voter ID / Licence',
                    icon: Icons.cake_outlined,
                    color: AppTheme.accentSaffron,
                    onTap: () => onNavigate(2),
                    width: cardWidth,
                  ),
                  _buildMetricCard(
                    title: 'Valid / Needs Review',
                    value: '$validRecords / $needsReview',
                    subtitle: 'Data quality on the currently loaded page',
                    icon: Icons.fact_check_outlined,
                    color: needsReview == 0 ? AppTheme.statusGreen : AppTheme.warningAmber,
                    onTap: () => onNavigate(1),
                    width: cardWidth,
                  ),
                  _buildMetricCard(
                    title: 'Service Catalogue',
                    value: '${state.services.length}',
                    subtitle: 'Catalogue entries loaded from the backend',
                    icon: Icons.account_balance_outlined,
                    color: AppTheme.statusGreen,
                    onTap: () => onNavigate(3),
                    width: cardWidth,
                  ),
                  _buildMetricCard(
                    title: 'Outbound Call Jobs',
                    value: '${callJobs.length}',
                    subtitle: '$simulatedCalls simulated, $queuedCalls queued, $completedCalls completed, $failedCalls failed; $awaitingReview need review',
                    icon: Icons.phone_forwarded_outlined,
                    color: AppTheme.primaryNavy,
                    onTap: () => onNavigate(4),
                    width: cardWidth,
                  ),
                ],
              );
            },
          ),
          const SizedBox(height: 32),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('Connections and readiness', style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold)),
                const SizedBox(height: 4),
                Text(state.backendHealth.isConnected ? 'Backend health is reachable; provider statuses below show configuration only and do not represent live connectivity.' : state.backendHealth.isDemoOnly ? 'Demo mode has no backend or provider connection.' : state.backendHealth.message, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondaryLight)),
                const SizedBox(height: 12),
                Wrap(spacing: 20, runSpacing: 12, children: state.backendHealth.integrations.entries.map((entry) => _integrationStatus(entry.key, entry.value)).toList()),
              ]),
            ),
          ),
          const SizedBox(height: 24),

          // Two column lower layout (responsive)
          LayoutBuilder(
            builder: (context, constraints) {
              final isWide = constraints.maxWidth > 900;

              final leftCard = Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Row(
                        children: [
                          Icon(
                            Icons.flash_on,
                            color: AppTheme.accentSaffron,
                            size: 20,
                          ),
                          SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              'Instant Milestone Demonstration',
                              style: TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                                color: AppTheme.textPrimaryLight,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      const Text(
                        'Test deterministic date-of-birth and eligibility behavior using a synthetic profile. This action does not place a call.',
                        style: TextStyle(
                          fontSize: 13,
                          color: AppTheme.textSecondaryLight,
                        ),
                      ),
                      const SizedBox(height: 16),
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: AppTheme.backgroundLight,
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: AppTheme.borderLight),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Target Candidate: ${milestoneCandidate?.fullName ?? 'No synthetic records loaded'}',
                              style: TextStyle(
                                fontWeight: FontWeight.bold,
                                fontSize: 13,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'Current Status: ${milestoneCandidate == null ? 'No candidate available' : 'Age ${milestoneCandidate.age}, ${milestoneCandidate.state} (${milestoneCandidate.id})'}',
                              style: TextStyle(
                                fontSize: 12,
                                color: Colors.grey.shade700,
                              ),
                            ),
                            const SizedBox(height: 8),
                            const Text(
                          'Action: Set DOB to exactly 18 years ago today and re-evaluate eligibility.',
                              style: TextStyle(
                                fontSize: 12,
                                fontStyle: FontStyle.italic,
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 16),
                      ElevatedButton.icon(
                        onPressed: milestoneCandidate == null ? null : () {
                          final today18YearsAgo = DateTime(
                            DateTime.now().year - 18,
                            DateTime.now().month,
                            DateTime.now().day,
                          );
                          state.simulateDobChange(milestoneCandidate.id, today18YearsAgo);
                          onNavigate(2);
                        },
                        icon: const Icon(Icons.play_arrow, size: 18),
                        label: const Text('Simulate milestone'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppTheme.primaryNavy,
                          foregroundColor: Colors.white,
                        ),
                      ),
                    ],
                  ),
                ),
              );

              final rightCard = Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Expanded(
                            child: Row(
                              children: [
                                Icon(
                                  Icons.record_voice_over_outlined,
                                  color: AppTheme.primaryNavy,
                                  size: 20,
                                ),
                                SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    'Recent Call Activity',
                                    style: TextStyle(
                                      fontSize: 16,
                                      fontWeight: FontWeight.bold,
                                      color: AppTheme.textPrimaryLight,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                          TextButton(
                            onPressed: () => onNavigate(4),
                            child: const Text('View All Calls'),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      if (callJobs.isEmpty)
                        const Padding(
                          padding: EdgeInsets.symmetric(vertical: 32),
                          child: Center(
                            child: Text(
                              'No simulated calls scheduled yet.',
                              style: TextStyle(
                                color: AppTheme.textSecondaryLight,
                              ),
                            ),
                          ),
                        )
                      else
                        ListView.separated(
                          shrinkWrap: true,
                          physics: const NeverScrollableScrollPhysics(),
                          itemCount: callJobs.take(3).length,
                          separatorBuilder: (context, index) =>
                              const Divider(height: 16),
                          itemBuilder: (context, index) {
                            final job = callJobs[index];
                            return Row(
                              children: [
                                CircleAvatar(
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
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        '${job.citizenName} (${job.triggerEvent})',
                                        style: const TextStyle(
                                          fontSize: 13,
                                          fontWeight: FontWeight.w600,
                                        ),
                                        overflow: TextOverflow.ellipsis,
                                        maxLines: 1,
                                      ),
                                      Text(
                                        'Idempotency Key: ${job.idempotencyKey}',
                                        style: const TextStyle(
                                          fontSize: 11,
                                          color: AppTheme.textSecondaryLight,
                                        ),
                                        overflow: TextOverflow.ellipsis,
                                        maxLines: 1,
                                      ),
                                    ],
                                  ),
                                ),
                                Container(
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 8,
                                    vertical: 3,
                                  ),
                                  decoration: BoxDecoration(
                                    color: job.isCompleted
                                        ? AppTheme.statusGreen.withValues(
                                            alpha: 0.1,
                                          )
                                        : AppTheme.accentSaffron.withValues(
                                            alpha: 0.15,
                                          ),
                                    borderRadius: BorderRadius.circular(4),
                                  ),
                                  child: Text(
                                    job.jobStatus,
                                    style: TextStyle(
                                      fontSize: 11,
                                      fontWeight: FontWeight.bold,
                                      color: job.isCompleted
                                          ? AppTheme.statusGreen
                                          : AppTheme.warningAmber,
                                    ),
                                  ),
                                ),
                              ],
                            );
                          },
                        ),
                    ],
                  ),
                ),
              );

              if (isWide) {
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(flex: 5, child: leftCard),
                    const SizedBox(width: 24),
                    Expanded(flex: 6, child: rightCard),
                  ],
                );
              } else {
                return Column(
                  children: [leftCard, const SizedBox(height: 24), rightCard],
                );
              }
            },
          ),
        ],
      ),
    );
  }

  Widget _buildMetricCard({
    required String title,
    required String value,
    required String subtitle,
    required IconData icon,
    required Color color,
    required VoidCallback onTap,
    required double width,
  }) {
    return SizedBox(
      width: width,
      child: Card(
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(10),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Expanded(
                      child: Text(
                        title,
                        style: const TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w500,
                          color: AppTheme.textSecondaryLight,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    Icon(icon, color: color, size: 20),
                  ],
                ),
                const SizedBox(height: 10),
                Text(
                  value,
                  style: TextStyle(
                    fontSize: 28,
                    fontWeight: FontWeight.bold,
                    color: color,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  subtitle,
                  style: const TextStyle(
                    fontSize: 11,
                    color: AppTheme.textSecondaryLight,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _integrationStatus(String name, String status) {
    final ready = status == 'healthy' || status == 'configured';
    return Row(mainAxisSize: MainAxisSize.min, children: [
      Icon(ready ? Icons.check_circle_outline : Icons.info_outline, size: 16, color: ready ? AppTheme.statusGreen : AppTheme.warningAmber),
      const SizedBox(width: 6),
      Text('$name: $status', style: const TextStyle(fontSize: 12)),
    ]);
  }
}
