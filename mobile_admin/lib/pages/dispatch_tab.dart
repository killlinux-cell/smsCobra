import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../services/admin_api.dart';
import '../theme/cobra_admin_theme.dart';
import '../widgets/admin_shimmer.dart';
import '../widgets/cobra_stagger.dart';
import '../widgets/glass_panel.dart';

class DispatchTab extends StatefulWidget {
  const DispatchTab({
    super.key,
    required this.api,
    required this.onSessionExpired,
    this.initialAssignmentId,
    this.onInitialAssignmentConsumed,
  });

  final AdminApi api;
  final Future<void> Function() onSessionExpired;
  final int? initialAssignmentId;
  final VoidCallback? onInitialAssignmentConsumed;

  @override
  State<DispatchTab> createState() => _DispatchTabState();
}

class _DispatchTabState extends State<DispatchTab> with SingleTickerProviderStateMixin {
  List<dynamic> _assignments = [];
  List<dynamic> _vigiles = [];
  bool _loading = true;
  bool _loadingCandidates = false;
  int? _assignmentId;
  int? _vigileId;
  bool _sending = false;
  late final AnimationController _staggerCtrl;

  @override
  void initState() {
    super.initState();
    _staggerCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 560),
    );
    _load();
  }

  @override
  void dispose() {
    _staggerCtrl.dispose();
    super.dispose();
  }

  String _timeShort(dynamic t) {
    if (t == null) return '';
    final s = t.toString();
    return s.length >= 5 ? s.substring(0, 5) : s;
  }

  String _statutFr(String? s) {
    switch (s) {
      case 'scheduled':
        return 'Planifié';
      case 'replaced':
        return 'Remplacé';
      case 'completed':
        return 'Terminé';
      case 'missed':
        return 'Manqué';
      default:
        return s ?? '—';
    }
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final a = await widget.api.fetchTodayAssignments();
      if (mounted) {
        setState(() {
          _assignments = a;
          _assignmentId = widget.initialAssignmentId;
          _vigileId = null;
          _vigiles = [];
        });
        widget.onInitialAssignmentConsumed?.call();
        if (_assignmentId != null) {
          await _loadCandidates(_assignmentId!);
        }
      }
    } on AdminSessionExpiredException {
      await widget.onSessionExpired();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Erreur de chargement des affectations.')),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) _staggerCtrl.forward(from: 0);
        });
      }
    }
  }

  Future<void> _loadCandidates(int assignmentId) async {
    setState(() => _loadingCandidates = true);
    try {
      final v = await widget.api.fetchDispatchCandidates(assignmentId);
      if (!mounted) return;
      setState(() {
        _vigiles = v;
        if (_vigileId != null &&
            !v.any((raw) => (raw as Map)['id'] == _vigileId)) {
          _vigileId = null;
        }
      });
    } on AdminSessionExpiredException {
      await widget.onSessionExpired();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Impossible de charger les vigiles disponibles.')),
        );
      }
    } finally {
      if (mounted) setState(() => _loadingCandidates = false);
    }
  }

  void _onAssignmentChanged(int? id) {
    setState(() {
      _assignmentId = id;
      _vigileId = null;
      _vigiles = [];
    });
    if (id != null) _loadCandidates(id);
  }

  Future<void> _submit() async {
    if (_assignmentId == null || _vigileId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Choisissez une affectation et un vigile remplaçant.')),
      );
      return;
    }
    setState(() => _sending = true);
    try {
      final detail = await widget.api.dispatchReplacement(
        assignmentId: _assignmentId!,
        replacementGuardId: _vigileId!,
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(detail)),
        );
        await _load();
      }
    } on AdminSessionExpiredException {
      await widget.onSessionExpired();
    } catch (e) {
      if (mounted) {
        final msg = e.toString().replaceFirst('Exception: ', '');
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(msg)),
        );
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return RefreshIndicator(
        color: CobraAdminColors.indigo,
        onRefresh: _load,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 100),
          children: const [
            AdminShimmerScope(child: DispatchFormSkeleton()),
          ],
        ),
      );
    }

    return RefreshIndicator(
      color: CobraAdminColors.indigo,
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 100),
        children: [
          cobraStaggerItem(
            controller: _staggerCtrl,
            index: 0,
            child: Text(
              'Dépêcher un remplaçant',
              style: GoogleFonts.outfit(
                fontSize: 22,
                fontWeight: FontWeight.w900,
                color: CobraAdminColors.ink,
              ),
            ),
          ),
          cobraStaggerItem(
            controller: _staggerCtrl,
            index: 1,
              child: Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(
                'Choisissez d’abord le poste : seuls les vigiles libres sur ce créneau '
                '(sans garde ailleurs, empreinte faciale OK) sont proposés.',
                style: GoogleFonts.outfit(
                  color: const Color(0xFF64748B),
                  fontSize: 13,
                  height: 1.4,
                ),
              ),
            ),
          ),
          cobraStaggerItem(
            controller: _staggerCtrl,
            index: 2,
            child: const SizedBox(height: 20),
          ),
          cobraStaggerItem(
            controller: _staggerCtrl,
            index: 3,
            child: GlassPanel(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '1. Poste concerné (aujourd’hui)',
                    style: GoogleFonts.outfit(fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(height: 8),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: const Color(0xFFE2E8F0)),
                    ),
                    child: DropdownButtonHideUnderline(
                      child: DropdownButton<int>(
                        isExpanded: true,
                        value: _assignmentId,
                        hint: const Text('Choisir une affectation…'),
                        borderRadius: BorderRadius.circular(12),
                        items: _assignments.map((raw) {
                          final m = raw as Map<String, dynamic>;
                          final id = (m['id'] as num).toInt();
                          final site = m['site_name'] ?? '';
                          final guard = m['guard_display'] ?? '';
                          final start = _timeShort(m['start_time']);
                          final end = _timeShort(m['end_time']);
                          final st = _statutFr(m['status']?.toString());
                          return DropdownMenuItem<int>(
                            value: id,
                            child: Text(
                              '$site · $start–$end · $guard · $st',
                              overflow: TextOverflow.ellipsis,
                              maxLines: 2,
                            ),
                          );
                        }).toList(),
                        onChanged: _onAssignmentChanged,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          cobraStaggerItem(
            controller: _staggerCtrl,
            index: 4,
            child: const SizedBox(height: 14),
          ),
          cobraStaggerItem(
            controller: _staggerCtrl,
            index: 5,
            child: GlassPanel(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '2. Vigile remplaçant',
                    style: GoogleFonts.outfit(fontWeight: FontWeight.w800),
                  ),
                  if (_assignmentId == null)
                    Padding(
                      padding: const EdgeInsets.only(top: 6),
                      child: Text(
                        'Sélectionnez un poste ci-dessus.',
                        style: GoogleFonts.outfit(
                          fontSize: 12,
                          color: const Color(0xFF64748B),
                        ),
                      ),
                    )
                  else if (_loadingCandidates)
                    const Padding(
                      padding: EdgeInsets.only(top: 12),
                      child: Center(
                        child: SizedBox(
                          width: 24,
                          height: 24,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        ),
                      ),
                    )
                  else if (_vigiles.isEmpty)
                    Padding(
                      padding: const EdgeInsets.only(top: 6),
                      child: Text(
                        'Aucun vigile disponible sur ce créneau '
                        '(tous occupés ou sans empreinte faciale).',
                        style: GoogleFonts.outfit(
                          fontSize: 12,
                          color: const Color(0xFFB45309),
                        ),
                      ),
                    )
                  else ...[
                    Padding(
                      padding: const EdgeInsets.only(top: 4, bottom: 6),
                      child: Text(
                        '${_vigiles.length} vigile(s) disponible(s)',
                        style: GoogleFonts.outfit(
                          fontSize: 12,
                          color: const Color(0xFF64748B),
                        ),
                      ),
                    ),
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.symmetric(horizontal: 12),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: const Color(0xFFE2E8F0)),
                      ),
                      child: DropdownButtonHideUnderline(
                        child: DropdownButton<int>(
                          isExpanded: true,
                          value: _vigileId,
                          hint: const Text('Choisir un vigile…'),
                          borderRadius: BorderRadius.circular(12),
                          items: _vigiles.map((raw) {
                            final m = raw as Map<String, dynamic>;
                            final id = (m['id'] as num).toInt();
                            final name =
                                (m['display_name'] ?? m['username'] ?? id).toString();
                            return DropdownMenuItem<int>(
                              value: id,
                              child: Text(name, overflow: TextOverflow.ellipsis),
                            );
                          }).toList(),
                          onChanged: (v) => setState(() => _vigileId = v),
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
          cobraStaggerItem(
            controller: _staggerCtrl,
            index: 6,
            child: const SizedBox(height: 22),
          ),
          cobraStaggerItem(
            controller: _staggerCtrl,
            index: 7,
            child: SizedBox(
              height: 52,
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: _sending ? null : _submit,
                style: FilledButton.styleFrom(
                  backgroundColor: CobraAdminColors.accent,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                ),
                icon: _sending
                    ? const SizedBox(
                        width: 22,
                        height: 22,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                      )
                    : const Icon(Icons.send_rounded),
                label: Text(
                  _sending ? 'Envoi…' : 'Confirmer le remplacement',
                  style: GoogleFonts.outfit(fontWeight: FontWeight.w700),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
