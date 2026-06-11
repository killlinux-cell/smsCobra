import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../services/admin_api.dart';
import '../theme/cobra_admin_theme.dart';

class AssignmentFormPage extends StatefulWidget {
  const AssignmentFormPage({
    super.key,
    required this.api,
    required this.onSessionExpired,
    this.existing,
    this.vigiles,
    this.sites,
  });

  final AdminApi api;
  final Future<void> Function() onSessionExpired;
  final Map<String, dynamic>? existing;
  final List<Map<String, dynamic>>? vigiles;
  final List<Map<String, dynamic>>? sites;

  bool get isEdit => existing != null;

  @override
  State<AssignmentFormPage> createState() => _AssignmentFormPageState();
}

class _AssignmentFormPageState extends State<AssignmentFormPage> {
  final _formKey = GlobalKey<FormState>();
  List<Map<String, dynamic>> _vigiles = [];
  List<Map<String, dynamic>> _sites = [];
  bool _loadingRefs = true;
  bool _saving = false;
  bool _deleting = false;

  String _planningMode = 'planifier';
  int _extraDays = 5;
  bool _createFixedPost = true;
  int? _guardId;
  int? _siteId;
  DateTime _shiftDate = DateTime.now();
  String _shiftType = 'day';

  static String _isoDate(DateTime d) =>
      '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  static String _displayDate(DateTime d) =>
      '${d.day.toString().padLeft(2, '0')}/${d.month.toString().padLeft(2, '0')}/${d.year}';

  @override
  void initState() {
    super.initState();
    final m = widget.existing;
    if (m != null) {
      _guardId = (m['guard'] as num?)?.toInt();
      _siteId = (m['site'] as num?)?.toInt();
      final rawDate = m['shift_date']?.toString();
      if (rawDate != null && rawDate.length >= 10) {
        _shiftDate = DateTime.tryParse(rawDate.substring(0, 10)) ?? DateTime.now();
      }
      _shiftType = (m['shift_type'] ?? 'day').toString();
    }
    _loadRefs();
  }

  Future<void> _loadRefs() async {
    if (widget.vigiles != null && widget.sites != null) {
      setState(() {
        _vigiles = widget.vigiles!;
        _sites = widget.sites!;
        _loadingRefs = false;
      });
      return;
    }
    try {
      final v = await widget.api.fetchVigiles();
      final s = await widget.api.fetchSites();
      if (!mounted) return;
      setState(() {
        _vigiles = v.map((e) => Map<String, dynamic>.from(e as Map)).toList();
        _sites = s.map((e) => Map<String, dynamic>.from(e as Map)).toList();
      });
    } on AdminSessionExpiredException {
      await widget.onSessionExpired();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Impossible de charger vigiles / sites.')),
        );
      }
    } finally {
      if (mounted) setState(() => _loadingRefs = false);
    }
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _shiftDate,
      firstDate: DateTime.now().subtract(const Duration(days: 7)),
      lastDate: DateTime.now().add(const Duration(days: 365)),
    );
    if (picked != null && mounted) setState(() => _shiftDate = picked);
  }

  Future<void> _submit() async {
    if (_guardId == null || _siteId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Choisissez un vigile et un site.')),
      );
      return;
    }
    setState(() => _saving = true);
    try {
      if (widget.isEdit) {
        await widget.api.updateAssignment(
          (widget.existing!['id'] as num).toInt(),
          {
            'guard': _guardId,
            'site': _siteId,
            'shift_date': _isoDate(_shiftDate),
            'shift_type': _shiftType,
          },
        );
        if (!mounted) return;
        Navigator.of(context).pop(true);
      } else {
        final resp = await widget.api.createAssignment({
          'planning_mode': _planningMode,
          'extra_days': _extraDays,
          'create_fixed_post': _createFixedPost,
          'guard': _guardId,
          'site': _siteId,
          'shift_date': _isoDate(_shiftDate),
          'shift_type': _shiftType,
        });
        if (!mounted) return;
        final detail = resp['detail']?.toString();
        if (detail != null && detail.isNotEmpty) {
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(detail)));
        }
        Navigator.of(context).pop(true);
      }
    } on AdminSessionExpiredException {
      await widget.onSessionExpired();
    } catch (e) {
      if (mounted) {
        final msg = e.toString().replaceFirst('Exception: ', '');
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _confirmDelete() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Supprimer ?', style: GoogleFonts.outfit(fontWeight: FontWeight.w800)),
        content: Text(
          'Cette affectation sera définitivement supprimée.',
          style: GoogleFonts.outfit(),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Annuler')),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Supprimer', style: TextStyle(color: Color(0xFFDC2626))),
          ),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    setState(() => _deleting = true);
    try {
      await widget.api.deleteAssignment((widget.existing!['id'] as num).toInt());
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } on AdminSessionExpiredException {
      await widget.onSessionExpired();
    } catch (e) {
      if (mounted) {
        final msg = e.toString().replaceFirst('Exception: ', '');
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
      }
    } finally {
      if (mounted) setState(() => _deleting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: CobraAdminColors.surface,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        foregroundColor: CobraAdminColors.ink,
        title: Text(
          widget.isEdit ? 'Modifier l\'affectation' : 'Nouvelle affectation',
          style: GoogleFonts.outfit(fontWeight: FontWeight.w800, fontSize: 18),
        ),
        actions: [
          if (widget.isEdit)
            IconButton(
              onPressed: _deleting ? null : _confirmDelete,
              icon: _deleting
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.delete_outline_rounded, color: Color(0xFFDC2626)),
            ),
        ],
      ),
      body: _loadingRefs
          ? const Center(child: CircularProgressIndicator(color: CobraAdminColors.indigo))
          : SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    if (!widget.isEdit) ...[
                      Text('Mode', style: _labelStyle()),
                      const SizedBox(height: 8),
                      SegmentedButton<String>(
                        segments: const [
                          ButtonSegment(value: 'planifier', label: Text('Planifier')),
                          ButtonSegment(value: 'extra', label: Text('Extra')),
                        ],
                        selected: {_planningMode},
                        onSelectionChanged: (s) => setState(() => _planningMode = s.first),
                        style: ButtonStyle(
                          textStyle: WidgetStatePropertyAll(
                            GoogleFonts.outfit(fontWeight: FontWeight.w700),
                          ),
                        ),
                      ),
                      if (_planningMode == 'extra') ...[
                        const SizedBox(height: 16),
                        Text('Durée (jours consécutifs)', style: _labelStyle()),
                        Slider(
                          value: _extraDays.toDouble(),
                          min: 1,
                          max: 14,
                          divisions: 13,
                          label: '$_extraDays j',
                          activeColor: CobraAdminColors.indigo,
                          onChanged: (v) => setState(() => _extraDays = v.round()),
                        ),
                      ],
                      if (_planningMode == 'planifier') ...[
                        const SizedBox(height: 8),
                        SwitchListTile(
                          contentPadding: EdgeInsets.zero,
                          title: Text(
                            'Créer poste titulaire fixe',
                            style: GoogleFonts.outfit(fontWeight: FontWeight.w600),
                          ),
                          subtitle: Text(
                            'Reconduction automatique des gardes',
                            style: GoogleFonts.outfit(fontSize: 12, color: const Color(0xFF64748B)),
                          ),
                          value: _createFixedPost,
                          activeThumbColor: CobraAdminColors.indigo,
                          onChanged: (v) => setState(() => _createFixedPost = v),
                        ),
                      ],
                      const SizedBox(height: 8),
                    ],
                    Text('Vigile', style: _labelStyle()),
                    const SizedBox(height: 6),
                    _dropdown<int>(
                      value: _guardId,
                      hint: 'Choisir un vigile',
                      items: _vigiles
                          .map(
                            (v) => DropdownMenuItem<int>(
                              value: (v['id'] as num?)?.toInt(),
                              child: Text(
                                (v['display_name'] ?? v['username'] ?? '—').toString(),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          )
                          .where((e) => e.value != null)
                          .toList(),
                      onChanged: (v) => setState(() => _guardId = v),
                    ),
                    const SizedBox(height: 16),
                    Text('Site', style: _labelStyle()),
                    const SizedBox(height: 6),
                    _dropdown<int>(
                      value: _siteId,
                      hint: 'Choisir un site',
                      items: _sites
                          .map(
                            (s) => DropdownMenuItem<int>(
                              value: (s['id'] as num?)?.toInt(),
                              child: Text(
                                (s['name'] ?? '—').toString(),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          )
                          .where((e) => e.value != null)
                          .toList(),
                      onChanged: (v) => setState(() => _siteId = v),
                    ),
                    const SizedBox(height: 16),
                    Text('Date de garde', style: _labelStyle()),
                    const SizedBox(height: 6),
                    OutlinedButton.icon(
                      onPressed: _pickDate,
                      icon: const Icon(Icons.calendar_today_rounded, size: 18),
                      label: Text(_displayDate(_shiftDate)),
                      style: OutlinedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 16),
                        foregroundColor: CobraAdminColors.ink,
                        side: const BorderSide(color: Color(0xFFE2E8F0)),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        textStyle: GoogleFonts.outfit(fontWeight: FontWeight.w700),
                      ),
                    ),
                    const SizedBox(height: 16),
                    Text('Créneau', style: _labelStyle()),
                    const SizedBox(height: 8),
                    SegmentedButton<String>(
                      segments: const [
                        ButtonSegment(value: 'day', icon: Icon(Icons.wb_sunny_outlined), label: Text('Jour')),
                        ButtonSegment(value: 'night', icon: Icon(Icons.nightlight_round), label: Text('Nuit')),
                      ],
                      selected: {_shiftType},
                      onSelectionChanged: (s) => setState(() => _shiftType = s.first),
                      style: ButtonStyle(
                        textStyle: WidgetStatePropertyAll(
                          GoogleFonts.outfit(fontWeight: FontWeight.w700),
                        ),
                      ),
                    ),
                    const SizedBox(height: 28),
                    FilledButton(
                      onPressed: _saving ? null : _submit,
                      style: FilledButton.styleFrom(
                        backgroundColor: CobraAdminColors.indigo,
                        padding: const EdgeInsets.symmetric(vertical: 16),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                      ),
                      child: _saving
                          ? const SizedBox(
                              height: 22,
                              width: 22,
                              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                            )
                          : Text(
                              widget.isEdit ? 'Enregistrer' : 'Créer l\'affectation',
                              style: GoogleFonts.outfit(fontWeight: FontWeight.w800, fontSize: 16),
                            ),
                    ),
                  ],
                ),
              ),
            ),
    );
  }

  TextStyle _labelStyle() => GoogleFonts.outfit(
        fontWeight: FontWeight.w700,
        fontSize: 13,
        color: const Color(0xFF64748B),
      );

  Widget _dropdown<T>({
    required T? value,
    required String hint,
    required List<DropdownMenuItem<T>> items,
    required ValueChanged<T?> onChanged,
  }) {
    final effective = items.any((e) => e.value == value) ? value : null;
    return InputDecorator(
      decoration: InputDecoration(
        hintText: hint,
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Color(0xFFE2E8F0)),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<T>(
          isExpanded: true,
          value: effective,
          hint: Text(hint, style: GoogleFonts.outfit(color: const Color(0xFF94A3B8))),
          items: items,
          onChanged: onChanged,
          style: GoogleFonts.outfit(fontWeight: FontWeight.w600, color: CobraAdminColors.ink),
        ),
      ),
    );
  }
}
