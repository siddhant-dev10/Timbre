import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../models/citizen.dart';
import '../../state/app_state.dart';

class SimulationScreen extends StatefulWidget {
  final AppState state;
  final ValueChanged<int>? onNavigate;

  const SimulationScreen({super.key, required this.state, this.onNavigate});

  @override
  State<SimulationScreen> createState() => _SimulationScreenState();
}

class _SimulationScreenState extends State<SimulationScreen> {
  Citizen? _targetCitizen;
  DateTime _selectedDob = DateTime.now();

  @override
  void initState() {
    super.initState();
    _initTarget();
  }

  void _initTarget() {
    final citizens = widget.state.citizens;
    if (citizens.isNotEmpty) {
      _targetCitizen = widget.state.selectedCitizen ?? citizens.first;
      _selectedDob = _targetCitizen!.dateOfBirth;
    }
  }

  void _setPresetTurn18() {
    final now = DateTime.now();
    setState(() {
      // Set to 18 years ago today
      _selectedDob = DateTime(now.year - 18, now.month, now.day);
    });
  }

  void _setPresetTurn17() {
    final now = DateTime.now();
    setState(() {
      // Set to 17 years ago today
      _selectedDob = DateTime(now.year - 17, now.month, now.day);
    });
  }

  Future<void> _pickCustomDob() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _selectedDob,
      firstDate: DateTime(1940),
      lastDate: DateTime.now(),
      helpText: 'SELECT SIMULATED DATE OF BIRTH',
    );
    if (picked != null) {
      setState(() {
        _selectedDob = picked;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = widget.state;
    final citizens = state.citizens;
    final simResult = state.lastSimulationResult;

    if (_targetCitizen == null && citizens.isNotEmpty) {
      _targetCitizen = citizens.first;
      _selectedDob = _targetCitizen!.dateOfBirth;
    }

    final simulatedAge = Citizen.calculateAge(_selectedDob);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          const Text(
            'Life-Event Simulation Cockpit',
            style: TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.bold,
              color: AppTheme.textPrimaryLight,
            ),
          ),
          const SizedBox(height: 4),
          const Text(
            'Simulate demographic milestone events (e.g. turning 18 years old) to test automated eligibility detection and idempotent outbound call dispatch.',
            style: TextStyle(fontSize: 13, color: AppTheme.textSecondaryLight),
          ),
          const SizedBox(height: 24),

          // Main Interactive Simulation Card
          Card(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    '1. Select Target Fictional Citizen',
                    style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 12),
                  if (citizens.isEmpty)
                    const Text('No citizens loaded.')
                  else
                    DropdownButtonFormField<Citizen>(
                      initialValue: citizens.firstWhere(
                        (c) => c.id == _targetCitizen?.id,
                        orElse: () => citizens.first,
                      ),
                      decoration: const InputDecoration(
                        labelText: 'Synthetic Citizen Profile',
                        prefixIcon: Icon(Icons.person_outline),
                      ),
                      items: citizens.map((c) {
                        return DropdownMenuItem<Citizen>(
                          value: c,
                          child: Text(
                            '${c.fullName} • Age ${c.age} (${c.state}) [${c.id}]',
                          ),
                        );
                      }).toList(),
                      onChanged: (selected) {
                        if (selected != null) {
                          setState(() {
                            _targetCitizen = selected;
                            _selectedDob = selected.dateOfBirth;
                          });
                        }
                      },
                    ),
                  const SizedBox(height: 24),

                  const Text(
                    '2. Configure Simulated Date of Birth & Milestone',
                    style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 12),

                  Wrap(
                    spacing: 12,
                    runSpacing: 8,
                    children: [
                      ActionChip(
                        avatar: const Icon(
                          Icons.cake,
                          size: 16,
                          color: AppTheme.statusGreen,
                        ),
                        label: const Text(
                          'Preset: Turn 18 Today (Cross Milestone)',
                        ),
                        onPressed: _setPresetTurn18,
                      ),
                      ActionChip(
                        avatar: const Icon(
                          Icons.history,
                          size: 16,
                          color: AppTheme.warningAmber,
                        ),
                        label: const Text('Preset: Turn 17 Today (Minor)'),
                        onPressed: _setPresetTurn17,
                      ),
                      ActionChip(
                        avatar: const Icon(Icons.calendar_month, size: 16),
                        label: const Text('Pick Custom Date of Birth'),
                        onPressed: _pickCustomDob,
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),

                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: AppTheme.backgroundLight,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: AppTheme.borderLight),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceAround,
                      children: [
                        Column(
                          children: [
                            const Text(
                              'Current Age',
                              style: TextStyle(
                                fontSize: 12,
                                color: AppTheme.textSecondaryLight,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              '${_targetCitizen?.age ?? '-'} years',
                              style: const TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ),
                        const Icon(Icons.arrow_forward, color: Colors.grey),
                        Column(
                          children: [
                            const Text(
                              'Simulated New DOB',
                              style: TextStyle(
                                fontSize: 12,
                                color: AppTheme.textSecondaryLight,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              '${_selectedDob.year}-${_selectedDob.month.toString().padLeft(2, '0')}-${_selectedDob.day.toString().padLeft(2, '0')}',
                              style: const TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ),
                        const Icon(Icons.arrow_forward, color: Colors.grey),
                        Column(
                          children: [
                            const Text(
                              'Simulated Resulting Age',
                              style: TextStyle(
                                fontSize: 12,
                                color: AppTheme.textSecondaryLight,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              '$simulatedAge years',
                              style: TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.bold,
                                color: simulatedAge >= 18
                                    ? AppTheme.statusGreen
                                    : AppTheme.warningAmber,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 24),

                  // Execute button
                  SizedBox(
                    width: double.infinity,
                    height: 48,
                    child: FilledButton.icon(
                      onPressed: state.isSimulating || _targetCitizen == null
                          ? null
                          : () {
                              state.simulateDobChange(
                                _targetCitizen!.id,
                                _selectedDob,
                              );
                            },
                      icon: state.isSimulating
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.white,
                              ),
                            )
                          : const Icon(Icons.play_circle_fill, size: 20),
                      label: Text(
                        state.isSimulating
                            ? 'Evaluating Event & Dispatching Job...'
                            : 'Trigger Life-Event Recalculation',
                        style: const TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 15,
                        ),
                      ),
                      style: FilledButton.styleFrom(
                        backgroundColor: AppTheme.primaryNavy,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 24),

          // Simulation Result Banner
          if (simResult != null) ...[
            const Text(
              'Simulation Execution Result',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            Card(
              color: simResult.eventDetected != null
                  ? AppTheme.statusGreen.withValues(alpha: 0.05)
                  : Colors.grey.shade50,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10),
                side: BorderSide(
                  color: simResult.eventDetected != null
                      ? AppTheme.statusGreen.withValues(alpha: 0.4)
                      : AppTheme.borderLight,
                  width: 1.5,
                ),
              ),
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(
                          simResult.eventDetected != null
                              ? Icons.verified
                              : Icons.info_outline,
                          color: simResult.eventDetected != null
                              ? AppTheme.statusGreen
                              : Colors.grey,
                          size: 24,
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                simResult.eventDetected != null
                                    ? 'Milestone Detected: ${simResult.eventDetected}'
                                    : 'Profile Updated (No New Milestone)',
                                style: const TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              Text(
                                'Citizen ${simResult.citizen.fullName} transitioned from age ${simResult.previousAge} to age ${simResult.newAge}.',
                                style: const TextStyle(
                                  fontSize: 13,
                                  color: AppTheme.textSecondaryLight,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                    const Divider(height: 24),

                    if (simResult.generatedCallJob != null) ...[
                      const Text(
                        'Idempotent Outbound Call Job Generated:',
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(6),
                          border: Border.all(color: AppTheme.borderLight),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Job ID: ${simResult.generatedCallJob!.id}',
                              style: const TextStyle(
                                fontSize: 12,
                                fontFamily: 'monospace',
                              ),
                            ),
                            Text(
                              'Idempotency Key: ${simResult.generatedCallJob!.idempotencyKey}',
                              style: const TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.bold,
                                color: AppTheme.primaryNavy,
                              ),
                            ),
                            Text(
                              'Status: ${simResult.generatedCallJob!.jobStatus}',
                              style: const TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.bold,
                                color: AppTheme.warningAmber,
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 12),
                      Wrap(
                        spacing: 12,
                        runSpacing: 8,
                        children: [
                          FilledButton.tonal(
                            onPressed: () {
                              if (widget.onNavigate != null) {
                                widget.onNavigate!(3); // Eligibility
                              }
                            },
                            child: const Text('View Unlocked Schemes'),
                          ),
                          OutlinedButton(
                            onPressed: () {
                              if (widget.onNavigate != null) {
                                widget.onNavigate!(4); // Call Monitor
                              }
                            },
                            child: const Text('Inspect in Call Monitor'),
                          ),
                        ],
                      ),
                    ] else ...[
                      const Text(
                        'No outbound call generated because age did not transition past the statutory 18-year threshold.',
                        style: TextStyle(
                          fontSize: 12,
                          color: AppTheme.textSecondaryLight,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
