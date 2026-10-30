import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../state/app_state.dart';

class ServicesScreen extends StatelessWidget {
  final AppState state;

  const ServicesScreen({super.key, required this.state});

  @override
  Widget build(BuildContext context) {
    final services = state.services;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Government Services & Statutory Knowledge Catalog',
            style: TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.bold,
              color: AppTheme.textPrimaryLight,
            ),
          ),
          const SizedBox(height: 4),
          const Text(
            'Verified official Indian public schemes with statutory authority, official URLs, and fee structures.',
            style: TextStyle(fontSize: 13, color: AppTheme.textSecondaryLight),
          ),
          const SizedBox(height: 24),

          if (services.isEmpty)
            const Center(child: CircularProgressIndicator())
          else
            ListView.separated(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: services.length,
              separatorBuilder: (context, index) => const SizedBox(height: 16),
              itemBuilder: (context, index) {
                final service = services[index];
                return Card(
                  child: Padding(
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
                                    service.serviceName,
                                    style: const TextStyle(
                                      fontSize: 18,
                                      fontWeight: FontWeight.bold,
                                      color: AppTheme.textPrimaryLight,
                                    ),
                                  ),
                                  Text(
                                    'Authority: ${service.administeringBody} • Code: ${service.serviceCode}',
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
                                color: AppTheme.primaryNavy.withValues(
                                  alpha: 0.08,
                                ),
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: Text(
                                service.statutoryFeeInr == 0
                                    ? 'STATUTORY FREE'
                                    : 'FEE: ₹${service.statutoryFeeInr}',
                                style: const TextStyle(
                                  fontSize: 11,
                                  fontWeight: FontWeight.bold,
                                  color: AppTheme.primaryNavy,
                                ),
                              ),
                            ),
                          ],
                        ),
                        const Divider(height: 20),
                        Text(
                          service.descriptionEnglish,
                          style: const TextStyle(fontSize: 13, height: 1.4),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'Hinglish explanation: "${service.descriptionHinglish}"',
                          style: TextStyle(
                            fontSize: 12,
                            fontStyle: FontStyle.italic,
                            color: Colors.grey.shade700,
                          ),
                        ),
                        const SizedBox(height: 16),
                        Row(
                          children: [
                            const Icon(
                              Icons.link,
                              size: 16,
                              color: AppTheme.primaryNavy,
                            ),
                            const SizedBox(width: 6),
                            SelectableText(
                              service.officialPortalUrl,
                              style: const TextStyle(
                                fontSize: 13,
                                color: AppTheme.primaryNavy,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            const Spacer(),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 8,
                                vertical: 3,
                              ),
                              decoration: BoxDecoration(
                                color: Colors.grey.shade200,
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(
                                'Mode: ${service.applicationMode}',
                                style: const TextStyle(
                                  fontSize: 11,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
        ],
      ),
    );
  }
}
