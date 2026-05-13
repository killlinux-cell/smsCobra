import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../services/admin_api.dart';
import '../theme/cobra_admin_theme.dart';
import '../widgets/admin_shimmer.dart';
import '../widgets/cobra_stagger.dart';
import '../widgets/glass_panel.dart';

class AlertsTab extends StatefulWidget {
  const AlertsTab({super.key, required this.api, required this.onSessionExpired});

  final AdminApi api;
  final Future<void> Function() onSessionExpired;

  @override
  State<AlertsTab> createState() => _AlertsTabState();
}

class _AlertsTabState extends State<AlertsTab> with TickerProviderStateMixin {
  late TabController _tabController;
  late AnimationController _staggerCtrl;
  List<dynamic> _open = [];
  List<dynamic> _other = [];
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
      final other = all.where((a) {
        final m = a as Map<String, dynamic>;
        return m['status'] != 'open';
      }).toList();
      if (mounted) {
        setState(() {
          _open = open;
          _other = other;
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

  Future<void> _ack(Map<String, dynamic> row) async {
    final id = (row['id'] as num).toInt();
    try {
      await widget.api.ackAlert(id);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Alerte n°$id acquittée.')),
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
                    'Acquitter (vu / pris en charge)',
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
                    : _open.isEmpty
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
                            children: _open
                                .asMap()
                                .entries
                                .map(
                                  (e) => cobraStaggerItem(
                                    controller: _staggerCtrl,
                                    index: e.key,
                                    child: _card(e.value as Map<String, dynamic>, canAck: true),
                                  ),
                                )
                                .toList(),
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
