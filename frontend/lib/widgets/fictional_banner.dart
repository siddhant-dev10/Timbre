import 'package:flutter/material.dart';

import '../core/theme/app_theme.dart';

/// Top safety banner stating that records are fictional demo data and no live dialing occurs.
class FictionalBanner extends StatelessWidget {
  const FictionalBanner({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      color: AppTheme.accentSaffron.withValues(alpha: 0.12),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: Row(
        children: [
          const Icon(
            Icons.shield_outlined,
            size: 16,
            color: AppTheme.primaryNavy,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: RichText(
              text: const TextSpan(
                style: TextStyle(
                  fontSize: 12,
                  color: AppTheme.textPrimaryLight,
                ),
                children: [
                  TextSpan(
                    text: 'DEMO SAFETY INVARIANT: ',
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      color: AppTheme.primaryNavy,
                    ),
                  ),
                  TextSpan(
                    text: 'All citizen profiles are 100% fictional. Simulated voice calls run in-app; no actual cellular calls are placed.',
                  ),
                ],
              ),
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(
              color: AppTheme.primaryNavy,
              borderRadius: BorderRadius.circular(4),
            ),
            child: const Text(
              'FICTIONAL DATA',
              style: TextStyle(
                color: Colors.white,
                fontSize: 10,
                fontWeight: FontWeight.bold,
                letterSpacing: 0.5,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
