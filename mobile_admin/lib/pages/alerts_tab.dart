import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../services/admin_api.dart';
import '../theme/cobra_admin_theme.dart';
import '../widgets/admin_shimmer.dart';
import '../widgets/cobra_stagger.dart';
import '../widgets/glass_panel.dart';

class AlertsTab extends StatefulWidget {
  const AlertsTab({
    super.key,
    required this.api,
    required this.onSessionExpired,
    this.onDispatchAssignment,
  });

  final AdminApi api;
  final Future<void> Function() onSessionExpired;
  final void Function(int assignmentId)? onDispatchAssignment;

  @override
  State<AlertsTab> createState() => _AlertsTabState();
}

class _AlertsTabState extends State<AlertsTab> with TickerProviderStateMixin {
  late TabController _tabController;
  late AnimationController _staggerCtrl;
  List<dynamic> _open = [];
  List<dynamic> _other = [];
  List<dynamic> _replacementNeeded = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _staggerCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 700),
    );
    _load();
  }

  @override
  void dispose() {
    _tabController.dispose();
    _staggerCtrl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final open = await widget.api.fetchAlerts(status: 'open');
      final all = await widget.api.fetchAlerts();
      final replacement = await widget.api.fetchReplacementNeeded();
      final other = all.where((a) {
        final m = a as Map<String, dynamic>;
        return m['status'] != 'open';
      }).toList();
      if (mounted) {
        setState(() {
          _open = open;
          _other = other;
          _replacementNeeded = replacement;
        });
      }
    } on AdminSessionExpiredException {
      await widget.onSessionExpired();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Erreur de chargement des alertes.')),
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

  String _statusFr(String? s) {
    switch (s) {
      case 'open':
        return 'Ouverte';
      case 'acknowledged':
        return 'Acquittée';
      case 'resolved':
        return 'Résolue';
      default:
        return s ?? '—';
    }
  }

  Future<String?> _pickPresenceDecision() async {
    return showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(
          'Décision de présence',
          style: GoogleFonts.outfit(fontWeight: FontWeight.w800),
        ),
        content: Text(
          'Comment enregistrer ce vigile dans les rapports ?',
          style: GoogleFonts.outfit(),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Annuler'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, 'absent'),
            child: Text(
              'Absent',
              style: GoogleFonts.outfit(
                fontWeight: FontWeight.w700,
                color: CobraAdminColors.danger,
              ),
            ),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, 'present'),
            style: FilledButton.styleFrom(backgroundColor: CobraAdminColors.success),
            child: const Text('Présent (justifié)'),
          ),
        ],
      ),
    );
  }

  Future<void> _ack(Map<String, dynamic> row) async {
    final decision = await _pickPresenceDecision();
    if (decision == null || !mounted) return;
    final id = (row['id'] as num).toInt();
    try {
      await widget.api.ackAlert(id, presenceDecision: decision);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              decision == 'absent'
                  ? 'Alerte n°$id — absence confirmée.'
                  : 'Alerte n°$id — présence justifiée.',
            ),
          ),
        );
        await _load();
      }
    } on AdminSessionExpiredException {
      await widget.onSessionExpired();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Impossible d'acquitter pour l'instant.")),
        );
      }
    }
  }

  Future<void> _ackReplacement(int assignmentId) async {
    final decision = await _pickPresenceDecision();
    if (decision == null || !mounted) return;
    try {
      await widget.api.ackReplacementAssignment(
        assignmentId,
        presenceDecision: decision,
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              decision == 'absent'
                  ? 'Retard — absence confirmée.'
                  : 'Retard — présence justifiée.',
            ),
          ),
        );
        await _load();
      }
    } on AdminSessionExpiredException {
      await widget.onSessionExpired();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Impossible d'acquitter pour l'instant.")),
        );
      }
    }
  }

  Widget _replacementCard(Map<String, dynamic> m) {
    final site = (m['site_name'] ?? 'Site').toString();
    final guard = (m['guard_display'] ?? 'Vigile').toString();
    final overdue = (m['minutes_overdue'] as num?)?.toInt() ?? 0;
    final assignmentId = (m['assignment_id'] as num?)?.toInt();

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: GlassPanel(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: CobraAdminColors.danger.withAlpha(35),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    'Remplacement à prévoir',
                    style: GoogleFonts.outfit(
                      fontWeight: FontWeight.w700,
                      fontSize: 12,
                      color: CobraAdminColors.danger,
                    ),
                  ),
                ),
                const Spacer(),
                if (overdue > 0)
                  Text(
                    '+$overdue min',
                    style: GoogleFonts.outfit(
                      fontWeight: FontWeight.w700,
                      color: CobraAdminColors.danger,
                      fontSize: 12,
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 10),
            Text(site, style: GoogleFonts.outfit(fontWeight: FontWeight.w800, fontSize: 16)),
            Text(guard, style: GoogleFonts.outfit(color: const Color(0xFF64748B), fontSize: 14)),
            if (assignmentId != null) ...[
              const SizedBox(height: 12),
              Row(
                children: [
                  if (widget.onDispatchAssignment != null)
                    Expanded(
                      child: FilledButton.icon(
                        onPressed: () => widget.onDispatchAssignment!(assignmentId),
                        icon: const Icon(Icons.swap_horiz_rounded, size: 20),
                        label: const Text('Dépêcher'),
                        style: FilledButton.styleFrom(
                          backgroundColor: CobraAdminColors.accent,
                        ),
                      ),
                    ),
                  if (widget.onDispatchAssignment != null) const SizedBox(width: 8),
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () => _ackReplacement(assignmentId),
                      icon: const Icon(Icons.check_circle_outline_rounded, size: 20),
                      label: const Text('Décider'),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: CobraAdminColors.success,
                        side: BorderSide(color: CobraAdminColors.success.withAlpha(180)),
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _card(Map<String, dynamic> m, {required bool canAck}) {
    final site = (m['site_name'] ?? 'Site').toString();
    final guard = (m['guard_display'] ?? 'Vigile').toString();
    final msg = (m['message'] ?? '').toString();
    final triggered = (m['triggered_at'] ?? '').toString();
    final id = (m['id'] as num).toInt();
    final st = m['status']?.toString();

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: GlassPanel(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: st == 'open' ? CobraAdminColors.danger.withAlpha(30) : Colors.grey.withAlpha(40),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    _statusFr(st),
                    style: GoogleFonts.outfit(
                      fontWeight: FontWeight.w700,
                      fontSize: 12,
                      color: st == 'open' ? CobraAdminColors.danger : const Color(0xFF64748B),
                    ),
                  ),
                ),
                const Spacer(),
                Text(
                  '#$id',
                  style: GoogleFonts.outfit(
                    fontWeight: FontWeight.w600,
                    color: const Color(0xFF94A3B8),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Text(
              site,
              style: GoogleFonts.outfit(fontWeight: FontWeight.w800, fontSize: 16),
            ),
            Text(
              guard,
              style: GoogleFonts.outfit(color: const Color(0xFF64748B), fontSize: 14),
            ),
            const SizedBox(height: 8),
            Text(
              msg,
              style: GoogleFonts.outfit(fontSize: 14, height: 1.35),
            ),
            if (triggered.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Text(
                  triggered.replaceFirst('T', ' ').split('.').first,
                  style: GoogleFonts.outfit(
                    fontSize: 11,
                    color: const Color(0xFF94A3B8),
                  ),
                ),
              ),
            if (canAck) ...[
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: () => _ack(m),
                  icon: const Icon(Icons.check_circle_outline_rounded, size: 20),
                  label: Text(
                    'Décider présence / absence',
                    style: GoogleFonts.outfit(fontWeight: FontWeight.w600),
                  ),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: CobraAdminColors.success,
                    side: const BorderSide(color: CobraAdminColors.success),
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Material(
          color: Colors.transparent,
          child: TabBar(
            controller: _tabController,
            labelColor: CobraAdminColors.indigo,
            unselectedLabelColor: const Color(0xFF64748B),
            indicatorColor: CobraAdminColors.indigo,
            labelStyle: GoogleFonts.outfit(fontWeight: FontWeight.w700, fontSize: 14),
            unselectedLabelStyle: GoogleFonts.outfit(
              fontWeight: FontWeight.w600,
              fontSize: 14,
            ),
            tabs: const [
              Tab(text: 'À traiter'),
              Tab(text: 'Historique'),
            ],
          ),
        ),
        Expanded(
          child: TabBarView(
            controller: _tabController,
            children: [
              RefreshIndicator(
                color: CobraAdminColors.indigo,
                onRefresh: _load,
                child: _loading
                    ? ListView(
                        padding: const EdgeInsets.all(16),
                        children: const [
                          AdminShimmerScope(
                            child: Column(
                              children: [
                                ListRowSkeletonCard(),
                                ListRowSkeletonCard(),
                                ListRowSkeletonCard(),
                              ],
                            ),
                          ),
                        ],
                      )
                    : _open.isEmpty && _replacementNeeded.isEmpty
                        ? ListView(
                            children: [
                              const SizedBox(height: 80),
                              Center(
                                child: Text(
                                  'Aucune alerte ouverte.\nTout est sous contrôle.',
                                  textAlign: TextAlign.center,
                                  style: GoogleFonts.outfit(color: const Color(0xFF64748B)),
                                ),
                              ),
                            ],
                          )
                        : ListView(
                            padding: const EdgeInsets.all(16),
                            children: [
                              if (_replacementNeeded.isNotEmpty) ...[
                                Text(
                                  'Postes sans prise de service',
                                  style: GoogleFonts.outfit(
                                    fontWeight: FontWeight.w800,
                                    fontSize: 15,
                                  ),
                                ),
                                const SizedBox(height: 8),
                                ..._replacementNeeded.map(
                                  (r) => _replacementCard(
                                    Map<String, dynamic>.from(r as Map),
                                  ),
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  'Alertes ouvertes',
                                  style: GoogleFonts.outfit(
                                    fontWeight: FontWeight.w800,
                                    fontSize: 15,
                                  ),
                                ),
                                const SizedBox(height: 8),
                              ],
                              ..._open.asMap().entries.map(
                                    (e) => cobraStaggerItem(
                                      controller: _staggerCtrl,
                                      index: e.key,
                                      child: _card(
                                        e.value as Map<String, dynamic>,
                                        canAck: true,
                                      ),
                                    ),
                                  ),
                            ],
                          ),
              ),
              RefreshIndicator(
                color: CobraAdminColors.indigo,
                onRefresh: _load,
                child: _loading
                    ? ListView(
                        padding: const EdgeInsets.all(16),
                        children: const [
                          AdminShimmerScope(
                            child: Column(
                              children: [
                                ListRowSkeletonCard(),
                                ListRowSkeletonCard(),
                                ListRowSkeletonCard(),
                              ],
                            ),
                          ),
                        ],
                      )
                    : ListView(
                        padding: const EdgeInsets.all(16),
                        children: _other.isEmpty
                            ? [
                                const SizedBox(height: 80),
                                Center(
                                  child: Text(
                                    'Pas encore d’historique.',
                                    style: GoogleFonts.outfit(color: const Color(0xFF64748B)),
                                  ),
                                ),
                              ]
                            : _other
                                .asMap()
                                .entries
                                .map(
                                  (e) => cobraStaggerItem(
                                    controller: _staggerCtrl,
                                    index: e.key,
                                    child: _card(e.value as Map<String, dynamic>, canAck: false),
                                  ),
                                )
                                .toList(),
                      ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
