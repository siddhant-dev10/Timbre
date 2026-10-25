import 'package:flutter/material.dart';

import '../core/config/app_config.dart';
import '../core/theme/app_theme.dart';
import '../services/backend_health.dart';
import '../state/app_state.dart';

/// Interactive status pill displaying the backend connectivity state.
class BackendHealthPill extends StatelessWidget {
  final AppState state;

  const BackendHealthPill({super.key, required this.state});

  @override
  Widget build(BuildContext context) {
    final health = state.backendHealth;

    Color badgeColor;
    IconData icon;
    String label;

    switch (health.state) {
      case BackendConnectionState.connected:
        badgeColor = AppTheme.statusGreen;
        icon = Icons.check_circle_outline;
        label = 'Backend Connected (${health.latencyMs}ms)';
        break;
      case BackendConnectionState.checking:
        badgeColor = AppTheme.warningAmber;
        icon = Icons.sync;
        label = 'Connecting...';
        break;
      case BackendConnectionState.demoOnly:
        badgeColor = AppTheme.primaryNavy;
        icon = Icons.storage_outlined;
        label = 'Local Demo Mode';
        break;
      case BackendConnectionState.disconnected:
        badgeColor = AppTheme.errorRed;
        icon = Icons.error_outline;
        label = 'Backend Offline';
        break;
    }

    return InkWell(
      onTap: () => _showBackendSettingsDialog(context),
      borderRadius: BorderRadius.circular(20),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: badgeColor.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: badgeColor.withValues(alpha: 0.4),
            width: 1,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 14, color: badgeColor),
            const SizedBox(width: 6),
            Text(
              label,
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: badgeColor,
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _showBackendSettingsDialog(BuildContext context) {
    final urlController = TextEditingController(text: AppConfig.backendUrl);

    showDialog(
      context: context,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              title: const Row(
                children: [
                  Icon(Icons.settings_ethernet, color: AppTheme.primaryNavy),
                  SizedBox(width: 8),
                  Text('Backend & Connectivity Settings'),
                ],
              ),
              content: SizedBox(
                width: 480,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Configure connection to the ASUS TUF FastAPI backend service or run with in-memory demo data.',
                      style: TextStyle(
                        fontSize: 13,
                        color: AppTheme.textSecondaryLight,
                      ),
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: urlController,
                      decoration: const InputDecoration(
                        labelText: 'FastAPI Backend URL',
                        hintText: 'http://192.168.x.x:8000/api/v1',
                        prefixIcon: Icon(Icons.link),
                      ),
                    ),
                    const SizedBox(height: 16),
                    SwitchListTile(
                      contentPadding: EdgeInsets.zero,
                      title: const Text('Use Isolated Demo Mode'),
                      subtitle: const Text(
                        'Uses local synthetic citizens & rule engine without requiring ASUS backend.',
                        style: TextStyle(fontSize: 12),
                      ),
                      value: state.isDemoMode,
                      onChanged: (val) {
                        state.setMode(val);
                        setDialogState(() {});
                      },
                    ),
                    const Divider(height: 24),
                    Text(
                      'Status: ${state.backendHealth.message}',
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () {
                    state.checkBackendHealth();
                    Navigator.of(ctx).pop();
                  },
                  child: const Text('Test Connection'),
                ),
                FilledButton(
                  onPressed: () {
                    state.setBackendUrl(urlController.text.trim());
                    Navigator.of(ctx).pop();
                  },
                  child: const Text('Save & Apply'),
                ),
              ],
            );
          },
        );
      },
    );
  }
}
