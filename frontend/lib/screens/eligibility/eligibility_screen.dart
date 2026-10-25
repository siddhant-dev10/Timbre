import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../models/citizen.dart';
import '../../models/eligibility_result.dart';
import '../../state/app_state.dart';

class EligibilityScreen extends StatelessWidget {
  final AppState state;

  const EligibilityScreen({super.key, required this.state});

  @override
  Widget build(BuildContext context) {
    final citizens = state.citizens;
    final selected = state.selectedCitizen;
    final results = state.getEligibilityForSelected();

    return SingleChildScrollView(
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
                    'Scheme Eligibility Engine',
                    style: TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                      color: AppTheme.textPrimaryLight,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Evaluated using ${state.repository.dataSourceDescription}',
                    style: const TextStyle(
                      fontSize: 13,
                      color: AppTheme.textSecondaryLight,
                    ),
                  ),
                ],
              ),
              if (selected != null)
                FilledButton.icon(
                  onPressed: state.isLoadingEligibility
                      ? null
                      : () => state.loadEligibilityForCitizen(selected.id),
                  icon: const Icon(Icons.refresh, size: 18),
                  label: const Text('Re-evaluate Rules'),
                  style: FilledButton.styleFrom(
                    backgroundColor: AppTheme.primaryNavy,
                  ),
                ),
            ],
          ),
          const SizedBox(height: 20),

          // Citizen Switcher Bar
          if (citizens.isNotEmpty)
            Card(
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 8,
                ),
                child: Row(
                  children: [
                    const Icon(
                      Icons.person,
                      color: AppTheme.primaryNavy,
                      size: 20,
                    ),
                    const SizedBox(width: 12),
                    const Text(
                      'Evaluating Citizen: ',
                      style: TextStyle(
                        fontWeight: FontWeight.w600,
                        fontSize: 13,
                      ),
                    ),
                    Expanded(
                      child: DropdownButton<Citizen>(
                        isExpanded: true,
                        underline: const SizedBox(),
                        value: selected,
                        items: citizens.map((c) {
                          return DropdownMenuItem<Citizen>(
                            value: c,
                            child: Text(
                              '${c.fullName} • Age ${c.age} (${c.state}) [${c.id}]',
                              style: const TextStyle(fontSize: 13),
                            ),
                          );
                        }).toList(),
                        onChanged: (c) {
                          if (c != null) state.selectCitizen(c);
                        },
                      ),
                    ),
                  ],
                ),
              ),
            ),
          const SizedBox(height: 20),

          // Main Results Content
          if (state.isLoadingEligibility)
            const Center(
              child: Padding(
                padding: EdgeInsets.all(48),
                child: CircularProgressIndicator(),
              ),
            )
          else if (state.eligibilityError != null)
            Center(
              child: Column(
                children: [
                  const Icon(
                    Icons.error_outline,
                    size: 40,
                    color: AppTheme.errorRed,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Error: ${state.eligibilityError}',
                    style: const TextStyle(color: AppTheme.errorRed),
                  ),
                ],
              ),
            )
          else if (results.isEmpty)
            const Center(
              child: Padding(
                padding: EdgeInsets.all(32),
                child: Text(
                  'No eligibility evaluations found for this citizen.',
                ),
              ),
            )
          else
            ListView.separated(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: results.length,
              separatorBuilder: (context, index) => const SizedBox(height: 16),
              itemBuilder: (context, index) {
                return _buildSchemeResultCard(results[index]);
              },
            ),
        ],
      ),
    );
  }

  Widget _buildSchemeResultCard(EligibilityResult result) {
    final scheme = result.service;
    final isEligible = result.isEligible;

    return Card(
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(10),
        side: BorderSide(
          color: isEligible
              ? AppTheme.statusGreen.withValues(alpha: 0.4)
              : AppTheme.borderLight,
          width: isEligible ? 1.5 : 1,
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                CircleAvatar(
                  backgroundColor: isEligible
                      ? AppTheme.statusGreen.withValues(alpha: 0.12)
                      : Colors.grey.shade200,
                  radius: 20,
                  child: Icon(
                    isEligible ? Icons.check_circle : Icons.lock_clock,
                    color: isEligible
                        ? AppTheme.statusGreen
                        : Colors.grey.shade600,
                    size: 22,
                  ),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Expanded(
                            child: Text(
                              scheme.serviceName,
                              style: const TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                                color: AppTheme.textPrimaryLight,
                              ),
                            ),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 10,
                              vertical: 4,
                            ),
                            decoration: BoxDecoration(
                              color: isEligible
                                  ? AppTheme.statusGreen.withValues(alpha: 0.12)
                                  : Colors.grey.shade200,
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Text(
                              isEligible ? 'QUALIFIED' : 'NOT ELIGIBLE',
                              style: TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.bold,
                                color: isEligible
                                    ? AppTheme.statusGreen
                                    : Colors.grey.shade700,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 2),
                      Text(
                        'Authority: ${scheme.administeringBody} • Code: ${scheme.serviceCode}',
                        style: const TextStyle(
                          fontSize: 12,
                          color: AppTheme.textSecondaryLight,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const Divider(height: 24),

            // Rationale
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: isEligible
                    ? AppTheme.statusGreen.withValues(alpha: 0.05)
                    : Colors.grey.shade50,
                borderRadius: BorderRadius.circular(6),
              ),
              child: Row(
                children: [
                  Icon(
                    Icons.info_outline,
                    size: 16,
                    color: isEligible
                        ? AppTheme.statusGreen
                        : AppTheme.textSecondaryLight,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      result.qualificationReason,
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w500,
                        color: isEligible
                            ? AppTheme.statusGreen
                            : AppTheme.textPrimaryLight,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),

            // Details metadata
            Wrap(
              spacing: 24,
              runSpacing: 8,
              children: [
                _buildMetadataItem(
                  'Statutory Fee',
                  scheme.statutoryFeeInr == 0
                      ? 'Free (₹0)'
                      : '₹${scheme.statutoryFeeInr}',
                ),
                _buildMetadataItem('Application Mode', scheme.applicationMode),
                _buildMetadataItem(
                  'Age Requirement',
                  '>= ${scheme.minAge} years',
                ),
                _buildMetadataItem('Official Portal', scheme.officialPortalUrl),
              ],
            ),
            const SizedBox(height: 16),

            // Required docs
            if (scheme.requiredDocs.isNotEmpty) ...[
              const Text(
                'Mandatory Supporting Documents:',
                style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 6),
              Wrap(
                spacing: 8,
                runSpacing: 6,
                children: scheme.requiredDocs.map((doc) {
                  return Chip(
                    label: Text(doc, style: const TextStyle(fontSize: 11)),
                    padding: EdgeInsets.zero,
                    materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  );
                }).toList(),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildMetadataItem(String label, String value) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(
            fontSize: 11,
            color: AppTheme.textSecondaryLight,
          ),
        ),
        const SizedBox(height: 2),
        Text(
          value,
          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
        ),
      ],
    );
  }
}
