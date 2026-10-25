import 'package:flutter/material.dart';

import 'core/theme/app_theme.dart';
import 'screens/shell/app_shell.dart';
import 'state/app_state.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final appState = AppState();
  await appState.init();
  runApp(TimbreApp(state: appState));
}

class TimbreApp extends StatelessWidget {
  final AppState state;

  const TimbreApp({super.key, required this.state});

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: state,
      builder: (context, _) {
        return MaterialApp(
          title: 'Timbre — AI Government-Services Assistant',
          debugShowCheckedModeBanner: false,
          theme: AppTheme.lightTheme,
          home: AppShell(state: state),
        );
      },
    );
  }
}
