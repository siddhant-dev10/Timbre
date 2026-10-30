import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

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
                      'Citizen Records',
                      style: TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.textPrimaryLight,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '${state.citizensTotal} ${state.showArchived ? 'archived' : 'active'} records. Synthetic and real profiles are labelled separately.',
                      style: const TextStyle(
                        fontSize: 13,
                        color: AppTheme.textSecondaryLight,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 16),
              if (!state.isDemoMode) FilterChip(
                label: Text(state.showArchived ? 'Archived' : 'Active'),
                selected: state.showArchived,
                onSelected: state.setShowArchived,
              ),
              if (!state.isDemoMode) const SizedBox(width: 8),
              if (!state.isDemoMode) ...[
                OutlinedButton.icon(onPressed: _importFile, icon: const Icon(Icons.upload_file), label: const Text('Import')),
                const SizedBox(width: 8),
                OutlinedButton.icon(onPressed: () => _export('csv'), icon: const Icon(Icons.download), label: const Text('Export CSV')),
                const SizedBox(width: 8),
                FilledButton.icon(onPressed: () => _editRecord(), icon: const Icon(Icons.add), label: const Text('Add record')),
                const SizedBox(width: 8),
              ],
              IconButton.outlined(tooltip: 'Refresh Registry', onPressed: () => state.loadCitizens(), icon: const Icon(Icons.refresh, size: 20)),
            ],
          ),
          const SizedBox(height: 16),

          // Search Field
          Row(children: [
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
            const SizedBox(width: 12),
            DropdownButton<String>(value: state.sortBy, onChanged: (value) { if (value != null) state.setCitizenSort(value); }, items: const [DropdownMenuItem(value: 'id', child: Text('Sort: ID')), DropdownMenuItem(value: 'name', child: Text('Sort: name')), DropdownMenuItem(value: 'age', child: Text('Sort: age')), DropdownMenuItem(value: 'state', child: Text('Sort: state'))]),
            IconButton(tooltip: state.sortBy == 'id' ? 'Toggle sort order' : 'Toggle sort order', onPressed: () => state.setCitizenSort(state.sortBy), icon: const Icon(Icons.swap_vert)),
          ]),
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
                          child: Column(children: [
                            Expanded(child: ListView.separated(
                            itemCount: citizens.length,
                            separatorBuilder: (context, index) => const Divider(height: 1),
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
                                      child: Text(
                                        citizen.isFictional ? 'SYNTHETIC' : 'REAL',
                                        style: const TextStyle(
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
                          )),
                            if (!state.isDemoMode) Padding(
                              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                              child: Row(mainAxisAlignment: MainAxisAlignment.end, children: [
                                Text('Showing ${state.citizensOffset + 1}–${state.citizensOffset + citizens.length} of ${state.citizensTotal}', style: const TextStyle(fontSize: 12)),
                                IconButton(tooltip: 'Previous page', onPressed: state.citizensOffset == 0 ? null : () => state.goToCitizenPage(state.citizensOffset - 100), icon: const Icon(Icons.chevron_left)),
                                IconButton(tooltip: 'Next page', onPressed: state.canLoadNextCitizenPage ? () => state.goToCitizenPage(state.citizensOffset + 100) : null, icon: const Icon(Icons.chevron_right)),
                              ]),
                            ),
                          ]),
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

  Future<void> _editRecord([Citizen? citizen]) async {
    final first = TextEditingController(text: citizen?.firstName ?? '');
    final last = TextEditingController(text: citizen?.lastName ?? '');
    final dob = TextEditingController(text: citizen == null ? '2000-01-01' : '${citizen.dateOfBirth.year.toString().padLeft(4, '0')}-${citizen.dateOfBirth.month.toString().padLeft(2, '0')}-${citizen.dateOfBirth.day.toString().padLeft(2, '0')}');
    final stateController = TextEditingController(text: citizen?.state ?? '');
    final district = TextEditingController(text: citizen?.district ?? '');
    final city = TextEditingController(text: citizen?.cityOrVillage ?? '');
    final formKey = GlobalKey<FormState>();
    final result = await showDialog<Map<String, String>>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(citizen == null ? 'Add synthetic record' : 'Edit record'),
        content: SizedBox(
          width: 440,
          child: Form(
            key: formKey,
            child: SingleChildScrollView(
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                TextFormField(controller: first, decoration: const InputDecoration(labelText: 'First name'), validator: (v) => v == null || v.trim().isEmpty ? 'Required' : null),
                TextFormField(controller: last, decoration: const InputDecoration(labelText: 'Last name'), validator: (v) => v == null || v.trim().isEmpty ? 'Required' : null),
                TextFormField(controller: dob, decoration: const InputDecoration(labelText: 'Date of birth (YYYY-MM-DD)'), validator: (v) { try { DateTime.parse(v!); return null; } catch (_) { return 'Use YYYY-MM-DD'; } }),
                TextFormField(controller: stateController, decoration: const InputDecoration(labelText: 'State'), validator: (v) => v == null || v.trim().isEmpty ? 'Required' : null),
                TextFormField(controller: district, decoration: const InputDecoration(labelText: 'District'), validator: (v) => v == null || v.trim().isEmpty ? 'Required' : null),
                TextFormField(controller: city, decoration: const InputDecoration(labelText: 'City or village'), validator: (v) => v == null || v.trim().isEmpty ? 'Required' : null),
                const SizedBox(height: 8),
                if (citizen == null) const Text('New records are synthetic demo profiles. Additional fields can be completed through an import file.', style: TextStyle(fontSize: 12)),
              ]),
            ),
          ),
        ),
        actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')), FilledButton(onPressed: () { if (formKey.currentState!.validate()) Navigator.pop(context, {'first_name': first.text.trim(), 'last_name': last.text.trim(), 'date_of_birth': dob.text.trim(), 'state': stateController.text.trim(), 'district': district.text.trim(), 'city_or_village': city.text.trim()}); }, child: const Text('Save'))],
      ),
    );
    first.dispose(); last.dispose(); dob.dispose(); stateController.dispose(); district.dispose(); city.dispose();
    if (result == null || !mounted) return;
    try {
      if (citizen == null) {
        await widget.state.createCitizen({...result, 'record_source': 'synthetic'});
      } else {
        await widget.state.updateCitizen(citizen.id, result);
      }
      _showFeedback(citizen == null ? 'Record added.' : 'Record updated.');
    } catch (e) { _showFeedback(e.toString()); }
  }

  Future<void> _importFile() async {
    final path = TextEditingController();
    final selectedPath = await showDialog<String>(context: context, builder: (context) => AlertDialog(
      title: const Text('Import CSV or JSON'),
      content: SizedBox(width: 420, child: TextField(controller: path, decoration: const InputDecoration(labelText: 'Full file path', hintText: '/Users/you/records.csv'))),
      actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')), FilledButton(onPressed: () => Navigator.pop(context, path.text.trim()), child: const Text('Validate and import'))],
    ));
    path.dispose();
    if (selectedPath == null || selectedPath.isEmpty) return;
    try {
      final result = await widget.state.importRecords(selectedPath);
      _showFeedback(result['committed'] == true ? 'Imported ${result['imported']} records.' : 'Import rejected. ${result['errors']}');
    } catch (e) { _showFeedback(e.toString()); }
  }

  Future<void> _export(String format) async {
    try {
      final data = await widget.state.exportRecords(format);
      if (!mounted) return;
      await showDialog<void>(context: context, builder: (context) => AlertDialog(
        title: Text('Export ${format.toUpperCase()}'),
        content: SizedBox(width: 600, height: 400, child: SelectableText(data, style: const TextStyle(fontFamily: 'monospace', fontSize: 11))),
        actions: [TextButton(onPressed: () async { await Clipboard.setData(ClipboardData(text: data)); if (context.mounted) Navigator.pop(context); }, child: const Text('Copy to clipboard')), FilledButton(onPressed: () => Navigator.pop(context), child: const Text('Close'))],
      ));
    } catch (e) { _showFeedback(e.toString()); }
  }

  void _showFeedback(String text) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text))); }

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

            if (!widget.state.isDemoMode) Row(children: [
              if (citizen.isArchived) OutlinedButton.icon(onPressed: () async { try { await widget.state.repository.restoreCitizen(citizen.id); await widget.state.setShowArchived(false); _showFeedback('Record restored.'); } catch (e) { _showFeedback(e.toString()); } }, icon: const Icon(Icons.unarchive_outlined, size: 16), label: const Text('Restore')),
              if (!citizen.isArchived) OutlinedButton.icon(onPressed: () => _editRecord(citizen), icon: const Icon(Icons.edit, size: 16), label: const Text('Edit')), const SizedBox(width: 8), if (!citizen.isArchived) TextButton.icon(onPressed: () async {
              final confirmed = await showDialog<bool>(context: context, builder: (context) => AlertDialog(title: const Text('Archive this record?'), content: const Text('The record will be hidden from the active list and can be restored through the API.'), actions: [TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')), FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Archive'))]));
              if (confirmed == true) { try { await widget.state.archiveCitizen(citizen.id); _showFeedback('Record archived.'); } catch (e) { _showFeedback(e.toString()); } }
            }, icon: const Icon(Icons.archive_outlined, size: 16), label: const Text('Archive'))]),

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
