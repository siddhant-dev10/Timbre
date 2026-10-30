import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../state/app_state.dart';
import '../../widgets/backend_health_pill.dart';
import '../../widgets/fictional_banner.dart';
import '../dashboard/dashboard_screen.dart';
import '../citizens/citizens_screen.dart';
import '../simulation/simulation_screen.dart';
import '../eligibility/eligibility_screen.dart';
import '../calls/call_monitor_screen.dart';
import '../services/services_screen.dart';
import '../chat/chat_screen.dart';

class AppShell extends StatefulWidget {
  final AppState state;

  const AppShell({super.key, required this.state});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int _currentIndex = 0;

  void _navigateTo(int index) {
    setState(() {
      _currentIndex = index;
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = widget.state;

    final pages = [
      DashboardScreen(state: state, onNavigate: _navigateTo),
      CitizensScreen(state: state, onNavigate: _navigateTo),
      SimulationScreen(state: state, onNavigate: _navigateTo),
      EligibilityScreen(state: state),
      CallMonitorScreen(state: state),
      ServicesScreen(state: state),
      ChatScreen(state: state),
    ];

    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: AppTheme.primaryNavy,
                borderRadius: BorderRadius.circular(6),
              ),
              child: const Icon(
                Icons.record_voice_over,
                color: Colors.white,
                size: 20,
              ),
            ),
            const SizedBox(width: 12),
            const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  'Timbre',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 0.5,
                  ),
                ),
                Text(
                  'AI Government-Services Assistant • Bharat Assist Cockpit',
                  style: TextStyle(
                    fontSize: 11,
                    color: AppTheme.textSecondaryLight,
                  ),
                ),
              ],
            ),
          ],
        ),
        actions: [
          BackendHealthPill(state: state),
          const SizedBox(width: 16),
        ],
      ),
      body: Column(
        children: [
          const FictionalBanner(),
          Expanded(
            child: Row(
              children: [
                NavigationRail(
                  selectedIndex: _currentIndex,
                  onDestinationSelected: _navigateTo,
                  extended: false,
                  labelType: NavigationRailLabelType.all,
                  destinations: const [
                    NavigationRailDestination(
                      icon: Icon(Icons.dashboard_outlined),
                      selectedIcon: Icon(Icons.dashboard),
                      label: Text('Overview'),
                    ),
                    NavigationRailDestination(
                      icon: Icon(Icons.people_alt_outlined),
                      selectedIcon: Icon(Icons.people_alt),
                      label: Text('Citizens'),
                    ),
                    NavigationRailDestination(
                      icon: Icon(Icons.bolt_outlined),
                      selectedIcon: Icon(Icons.bolt),
                      label: Text('Simulation'),
                    ),
                    NavigationRailDestination(
                      icon: Icon(Icons.verified_outlined),
                      selectedIcon: Icon(Icons.verified),
                      label: Text('Eligibility'),
                    ),
                    NavigationRailDestination(
                      icon: Icon(Icons.phone_forwarded_outlined),
                      selectedIcon: Icon(Icons.phone_forwarded),
                      label: Text('Calls'),
                    ),
                    NavigationRailDestination(
                      icon: Icon(Icons.account_balance_outlined),
                      selectedIcon: Icon(Icons.account_balance),
                      label: Text('Schemes'),
                    ),
                    NavigationRailDestination(
                      icon: Icon(Icons.chat_bubble_outline),
                      selectedIcon: Icon(Icons.chat_bubble),
                      label: Text('Chat'),
                    ),
                  ],
                ),
                const VerticalDivider(width: 1),
                Expanded(
                  child: AnimatedSwitcher(
                    duration: const Duration(milliseconds: 200),
                    child: pages[_currentIndex],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
