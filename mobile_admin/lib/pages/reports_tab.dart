import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../services/admin_api.dart';
import '../theme/cobra_admin_theme.dart';
import '../widgets/admin_shimmer.dart';
import '../widgets/cobra_stagger.dart';
import '../widgets/glass_panel.dart';

class ReportsTab extends StatefulWidget {
  const ReportsTab({super.key, required this.api, required this.onSessionExpired});

  final AdminApi api;
  final Future<void> Function() onSessionExpired;

  @override
  State<ReportsTab> createState() => _ReportsTabState();
}

class _ReportsTabState extends State<ReportsTab> with TickerProviderStateMixin {
  List<dynamic> _activityRows = [];
  List<dynamic> _reportRows = [];
  bool _loading = true;
  late final AnimationController _staggerCtrl;
  late final TabController _tabCtrl;

  @override
  void initState() {
    super.initState();
    _staggerCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 680),
    );
    _tabCtrl = TabController(length: 2, vsync: this);
    _load();
  }

  @override
  void dispose() {
    _tabCtrl.dispose();
    _staggerCtrl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final results = await Future.wait<List<dynamic>>([
        widget.api.fetchActivityFeed(limit: 80),
        widget.api.fetchReports(limit: 50),
      ]);
      if (!mounted) return;
      setState(() {
        _activityRows = results[0];
        _reportRows = results[1];
      });
    } on AdminSessionExpiredException {
      await widget.onSessionExpired();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Impossible de charger les rapports.')),
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

  String _formatOccurred(String? iso) {
    if (iso == null || iso.isEmpty) return '';
    try {
      final dt = DateTime.parse(iso).toLocal();
      final d = dt.day.toString().padLeft(2, '0');
      final m = dt.month.toString().padLeft(2, '0');
      final h = dt.hour.toString().padLeft(2, '0');
      final min = dt.minute.toString().padLeft(2, '0');
      return '$d/$m/${dt.year} · $h:$min';
    } catch (_) {
      return iso;
    }
  }

  (IconData, Color) _activityStyle(String kind) {
    switch (kind) {
      case 'site_created':
        return (Icons.domain_add_rounded, CobraAdminColors.indigo);
      case 'vigile_created':
        return (Icons.person_add_alt_1_rounded, const Color(0xFF0D9488));
      case 'assignment_planned':
        return (Icons.event_available_rounded, const Color(0xFF7C3AED));
      case 'guard_replaced':
        return (Icons.sync_alt_rounded, const Color(0xFFEA580C));
      case 'fixed_post_configured':
        return (Icons.push_pin_rounded, const Color(0xFF2563EB));
      default:
        return (Icons.article_rounded, const Color(0xFF64748B));
    }
  }

  Widget _buildActivityList() {
    if (_loading) {
      return ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 100),
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
      );
    }
    if (_activityRows.isEmpty) {
      return ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 100),
        children: [
          GlassPanel(
            child: Text(
              'Aucun événement récent. Les nouveaux sites, vigiles, affectations et remplacements apparaîtront ici.',
              style: GoogleFonts.outfit(color: const Color(0xFF64748B), fontSize: 14),
            ),
          ),
        ],
      );
    }
    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 100),
      itemCount: _activityRows.length,
      itemBuilder: (context, i) {
        final raw = _activityRows[i] as Map<String, dynamic>;
        final kind = (raw['kind'] ?? '').toString();
        final title = (raw['title'] ?? 'Événement').toString();
        final body = (raw['body'] ?? '').toString();
        final when = _formatOccurred(raw['occurred_at']?.toString());
        final style = _activityStyle(kind);
        return cobraStaggerItem(
          controller: _staggerCtrl,
          index: i + 2,
          child: Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: GlassPanel(
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: style.$2.withAlpha(36),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(style.$1, color: style.$2, size: 22),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          title,
                          style: GoogleFonts.outfit(
                            fontWeight: FontWeight.w800,
                            fontSize: 15,
                            color: CobraAdminColors.ink,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          body,
                          style: GoogleFonts.outfit(
                            fontSize: 13,
                            height: 1.35,
                            color: const Color(0xFF475569),
                          ),
                        ),
                        if (when.isNotEmpty) ...[
                          const SizedBox(height: 8),
                          Text(
                            when,
                            style: GoogleFonts.outfit(
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                              color: const Color(0xFF94A3B8),
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildPointageList() {
    if (_loading) {
      return ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 100),
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
      );
    }
    if (_reportRows.isEmpty) {
      return ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 100),
        children: [
          GlassPanel(
            child: Text(
              'Aucune synthèse de pointage pour le moment.',
              style: GoogleFonts.outfit(color: const Color(0xFF64748B)),
            ),
          ),
        ],
      );
    }
    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 100),
      itemCount: _reportRows.length,
      itemBuilder: (context, i) {
        final m = _reportRows[i] as Map<String, dynamic>;
        final site = (m['site_name'] ?? 'Site').toString();
        final guard = (m['guard_display'] ?? 'Vigile').toString();
        final date = (m['report_date'] ?? '').toString();
        final late = m['was_late'] == true;
        return cobraStaggerItem(
          controller: _staggerCtrl,
          index: i + 2,
          child: Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: GlassPanel(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          site,
                          style: GoogleFonts.outfit(
                            fontWeight: FontWeight.w800,
                            fontSize: 16,
                          ),
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: late
                              ? Colors.orange.withAlpha(40)
                              : CobraAdminColors.success.withAlpha(35),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(
                          late ? 'Retard' : 'À l’heure',
                          style: GoogleFonts.outfit(
                            fontSize: 11,
                            fontWeight: FontWeight.w700,
                            color: late ? Colors.orange.shade900 : CobraAdminColors.success,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(
                    guard,
                    style: GoogleFonts.outfit(color: const Color(0xFF64748B)),
                  ),
                  Text(
                    'Date : $date',
                    style: GoogleFonts.outfit(
                      fontSize: 12,
                      color: const Color(0xFF94A3B8),
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
          child: cobraStaggerItem(
            controller: _staggerCtrl,
            index: 0,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Rapports',
                  style: GoogleFonts.outfit(
                    fontSize: 22,
                    fontWeight: FontWeight.w900,
                    color: CobraAdminColors.ink,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  'Journal opérationnel (sites, personnel, affectations, remplacements) et synthèse des pointages.',
                  style: GoogleFonts.outfit(
                    color: const Color(0xFF64748B),
                    fontSize: 13,
                  ),
                ),
              ],
            ),
          ),
        ),
        cobraStaggerItem(
          controller: _staggerCtrl,
          index: 1,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(8, 12, 8, 0),
            child: TabBar(
              controller: _tabCtrl,
              labelColor: CobraAdminColors.indigo,
              unselectedLabelColor: const Color(0xFF64748B),
              indicatorColor: CobraAdminColors.indigo,
              labelStyle: GoogleFonts.outfit(fontWeight: FontWeight.w800, fontSize: 13),
              unselectedLabelStyle: GoogleFonts.outfit(fontWeight: FontWeight.w600, fontSize: 13),
              tabs: const [
                Tab(text: 'Activité'),
                Tab(text: 'Pointages'),
              ],
            ),
          ),
        ),
        Expanded(
          child: TabBarView(
            controller: _tabCtrl,
            children: [
              RefreshIndicator(
                color: CobraAdminColors.indigo,
                onRefresh: _load,
                child: _buildActivityList(),
              ),
              RefreshIndicator(
                color: CobraAdminColors.indigo,
                onRefresh: _load,
                child: _buildPointageList(),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
