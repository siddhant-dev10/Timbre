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
    final totalCitizens = citizens.length;
    final turning18Candidates = citizens.where((c) => c.age == 17).length;
    final adults = citizens.where((c) => c.isAdult).length;
    final completedCalls = callJobs.where((j) => j.isCompleted).length;
    final queuedCalls = callJobs.where((j) => j.isQueued).length;

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
                    title: 'Total Fictional Citizens',
                    value: '$totalCitizens',
                    subtitle:
                        '$adults adults (>= 18), $turning18Candidates milestone candidates',
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
                    title: 'Active Schemes',
                    value: '3',
                    subtitle: 'ECI Form 6, MoRTH Parivahan, PM-JAY',
                    icon: Icons.account_balance_outlined,
                    color: AppTheme.statusGreen,
                    onTap: () => onNavigate(3),
                    width: cardWidth,
                  ),
                  _buildMetricCard(
                    title: 'Outbound Call Jobs',
                    value: '${callJobs.length}',
                    subtitle: '$queuedCalls queued, $completedCalls completed',
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
                        'Test the core Timbre lifecycle flow: Advance Aarav Sharma’s date of birth to cross the age 18 threshold, evaluate Voter ID & Driving Licence qualification, and schedule an outbound call.',
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
                            const Text(
                              'Target Candidate: Aarav Sharma',
                              style: TextStyle(
                                fontWeight: FontWeight.bold,
                                fontSize: 13,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'Current Status: Age 17, Uttar Pradesh (cit-001)',
                              style: TextStyle(
                                fontSize: 12,
                                color: Colors.grey.shade700,
                              ),
                            ),
                            const SizedBox(height: 8),
                            const Text(
                              'Action: Set DOB to exactly 18 years ago today.',
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
                        onPressed: () {
                          // Find Aarav and trigger simulation
                          final aarav = state.citizens.firstWhere(
                            (c) => c.firstName == 'Aarav',
                            orElse: () => state.citizens.first,
                          );
                          final today18YearsAgo = DateTime(
                            DateTime.now().year - 18,
                            DateTime.now().month,
                            DateTime.now().day,
                          );
                          state.simulateDobChange(aarav.id, today18YearsAgo);
                          onNavigate(2);
                        },
                        icon: const Icon(Icons.play_arrow, size: 18),
                        label: const Text('Simulate Aarav Turning 18'),
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
}
