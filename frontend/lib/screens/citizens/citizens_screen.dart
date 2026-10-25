import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../models/citizen.dart';
import '../../state/app_state.dart';

class CitizensScreen extends StatefulWidget {
  final AppState state;
  final ValueChanged<int>? onNavigate;

  const CitizensScreen({super.key, required this.state, this.onNavigate});

  @override
  State<CitizensScreen> createState() => _CitizensScreenState();
}

class _CitizensScreenState extends State<CitizensScreen> {
  final _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _searchController.text = widget.state.searchQuery;
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = widget.state;
    final citizens = state.citizens;
    final selected = state.selectedCitizen;
    final eligibilityResults = state.getEligibilityForSelected();

    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Top action bar
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Fictional Citizen Registry',
                      style: TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.textPrimaryLight,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Showing ${citizens.length} synthetic profiles. Strict safety invariant enforced.',
                      style: const TextStyle(
                        fontSize: 13,
                        color: AppTheme.textSecondaryLight,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 16),
              IconButton.outlined(
                tooltip: 'Refresh Registry',
                onPressed: () => state.loadCitizens(),
                icon: const Icon(Icons.refresh, size: 20),
              ),
            ],
          ),
          const SizedBox(height: 16),

          // Search Field
          SizedBox(
            width: 400,
            child: TextField(
              controller: _searchController,
              onChanged: (val) => state.setSearchQuery(val),
              decoration: InputDecoration(
                hintText: 'Search by name, state, phone...',
                prefixIcon: const Icon(Icons.search, size: 20),
                suffixIcon: _searchController.text.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear, size: 18),
                        onPressed: () {
                          _searchController.clear();
                          state.setSearchQuery('');
                        },
                      )
                    : null,
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 10,
                ),
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Main split content
          Expanded(
            child: state.isLoadingCitizens
                ? const Center(child: CircularProgressIndicator())
                : state.citizensError != null
                ? _buildErrorView(state)
                : citizens.isEmpty
                ? _buildEmptyView()
                : Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Left: Citizens Table / List
                      Expanded(
                        flex: 6,
                        child: Card(
                          clipBehavior: Clip.antiAlias,
                          child: ListView.separated(
                            itemCount: citizens.length,
                            separatorBuilder: (context, index) =>
                                const Divider(height: 1),
                            itemBuilder: (context, index) {
                              final citizen = citizens[index];
                              final isSelected = selected?.id == citizen.id;

                              return ListTile(
                                selected: isSelected,
                                selectedTileColor: AppTheme.primaryNavy
                                    .withValues(alpha: 0.06),
                                leading: CircleAvatar(
                                  backgroundColor: citizen.isAdult
                                      ? AppTheme.primaryNavy.withValues(
                                          alpha: 0.1,
                                        )
                                      : AppTheme.accentSaffron.withValues(
                                          alpha: 0.2,
                                        ),
                                  child: Text(
                                    '${citizen.age}',
                                    style: TextStyle(
                                      fontSize: 12,
                                      fontWeight: FontWeight.bold,
                                      color: citizen.isAdult
                                          ? AppTheme.primaryNavy
                                          : AppTheme.warningAmber,
                                    ),
                                  ),
                                ),
                                title: Wrap(
                                  crossAxisAlignment: WrapCrossAlignment.center,
                                  spacing: 6,
                                  runSpacing: 4,
                                  children: [
                                    Text(
                                      citizen.fullName,
                                      style: const TextStyle(
                                        fontWeight: FontWeight.w600,
                                      ),
                                    ),
                                    Container(
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 5,
                                        vertical: 1,
                                      ),
                                      decoration: BoxDecoration(
                                        color: Colors.grey.shade200,
                                        borderRadius: BorderRadius.circular(3),
                                      ),
                                      child: const Text(
                                        'DEMO',
                                        style: TextStyle(
                                          fontSize: 9,
                                          fontWeight: FontWeight.bold,
                                        ),
                                      ),
                                    ),
                                    if (!citizen.isAdult)
                                      Container(
                                        padding: const EdgeInsets.symmetric(
                                          horizontal: 5,
                                          vertical: 1,
                                        ),
                                        decoration: BoxDecoration(
                                          color: AppTheme.accentSaffron
                                              .withValues(alpha: 0.2),
                                          borderRadius: BorderRadius.circular(
                                            3,
                                          ),
                                        ),
                                        child: const Text(
                                          'AGE 17',
                                          style: TextStyle(
                                            fontSize: 9,
                                            fontWeight: FontWeight.bold,
                                            color: AppTheme.warningAmber,
                                          ),
                                        ),
                                      ),
                                  ],
                                ),
                                subtitle: Text(
                                  '${citizen.state} • ${citizen.district} • ${citizen.phoneNumber}',
                                  style: const TextStyle(fontSize: 12),
                                ),
                                trailing: const Icon(
                                  Icons.chevron_right,
                                  size: 18,
                                ),
                                onTap: () => state.selectCitizen(citizen),
                              );
                            },
                          ),
                        ),
                      ),
                      const SizedBox(width: 20),

                      // Right: Detailed Inspection Sheet
                      Expanded(
                        flex: 5,
                        child: selected == null
                            ? const Card(
                                child: Center(
                                  child: Text(
                                    'Select a citizen to view details',
                                    style: TextStyle(
                                      color: AppTheme.textSecondaryLight,
                                    ),
                                  ),
                                ),
                              )
                            : _buildDetailPanel(selected, eligibilityResults),
                      ),
                    ],
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildDetailPanel(Citizen citizen, List<dynamic> eligibility) {
    return Card(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        citizen.fullName,
                        style: const TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      Text(
                        'ID: ${citizen.id} • Fictional Demo Profile',
                        style: const TextStyle(
                          fontSize: 12,
                          color: AppTheme.textSecondaryLight,
                        ),
                      ),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 4,
                  ),
                  decoration: BoxDecoration(
                    color: citizen.isAdult
                        ? AppTheme.statusGreen.withValues(alpha: 0.12)
                        : AppTheme.accentSaffron.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Text(
                    citizen.isAdult
                        ? 'Adult (Age ${citizen.age})'
                        : 'Minor (Age ${citizen.age})',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                      color: citizen.isAdult
                          ? AppTheme.statusGreen
                          : AppTheme.warningAmber,
                    ),
                  ),
                ),
              ],
            ),
            const Divider(height: 24),

            // Profile info grid
            _buildInfoRow(
              'Date of Birth',
              '${citizen.dateOfBirth.year}-${citizen.dateOfBirth.month.toString().padLeft(2, '0')}-${citizen.dateOfBirth.day.toString().padLeft(2, '0')}',
            ),
            _buildInfoRow('Gender', citizen.gender),
            _buildInfoRow('Phone', citizen.phoneNumber),
            _buildInfoRow(
              'State / District',
              '${citizen.state}, ${citizen.district}',
            ),
            _buildInfoRow('Pincode', citizen.pincode),
            _buildInfoRow('Income Bracket', citizen.simulatedIncomeBracket),

            const Divider(height: 24),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Expanded(
                  child: Text(
                    'Scheme Qualification Status',
                    style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold),
                  ),
                ),
                if (widget.state.isLoadingEligibility)
                  const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
              ],
            ),
            const SizedBox(height: 10),

            if (eligibility.isEmpty && !widget.state.isLoadingEligibility)
              const Text(
                'No schemes evaluated yet. Click below to run evaluation.',
                style: TextStyle(
                  fontSize: 12,
                  color: AppTheme.textSecondaryLight,
                ),
              )
            else
              ...eligibility.map((res) {
                final isEligible = res.isEligible as bool;
                return Container(
                  margin: const EdgeInsets.only(bottom: 8),
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: isEligible
                        ? AppTheme.statusGreen.withValues(alpha: 0.08)
                        : Colors.grey.shade100,
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(
                      color: isEligible
                          ? AppTheme.statusGreen.withValues(alpha: 0.3)
                          : Colors.grey.shade300,
                    ),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        isEligible ? Icons.check_circle : Icons.cancel_outlined,
                        size: 16,
                        color: isEligible ? AppTheme.statusGreen : Colors.grey,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              res.service.serviceName,
                              style: const TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            Text(
                              res.qualificationReason,
                              style: const TextStyle(
                                fontSize: 11,
                                color: AppTheme.textSecondaryLight,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                );
              }),

            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: () {
                if (widget.onNavigate != null) {
                  widget.onNavigate!(2); // Navigate to Life-Event simulation
                }
              },
              icon: const Icon(Icons.bolt, size: 16),
              label: Text('Simulate Life Event for ${citizen.firstName}'),
              style: FilledButton.styleFrom(
                backgroundColor: AppTheme.primaryNavy,
                minimumSize: const Size.fromHeight(40),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildInfoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: const TextStyle(
              fontSize: 12,
              color: AppTheme.textSecondaryLight,
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              value,
              textAlign: TextAlign.end,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w500),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildErrorView(AppState state) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.error_outline, size: 48, color: AppTheme.errorRed),
          const SizedBox(height: 12),
          Text(
            'Failed to load citizens: ${state.citizensError}',
            style: const TextStyle(color: AppTheme.errorRed),
          ),
          const SizedBox(height: 12),
          ElevatedButton(
            onPressed: () => state.loadCitizens(),
            child: const Text('Retry'),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyView() {
    return const Center(
      child: Text(
        'No citizens match your search filter.',
        style: TextStyle(color: AppTheme.textSecondaryLight),
      ),
    );
  }
}
