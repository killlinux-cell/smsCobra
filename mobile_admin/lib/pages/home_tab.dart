import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../services/admin_api.dart';
import '../theme/cobra_admin_theme.dart';
import '../widgets/admin_shimmer.dart';
import '../widgets/cobra_stagger.dart';
import '../widgets/glass_panel.dart';

class HomeTab extends StatefulWidget {
  const HomeTab({
    super.key,
    required this.api,
    required this.onRefreshAll,
    required this.onSessionExpired,
  });

  final AdminApi api;
  final VoidCallback onRefreshAll;
  final Future<void> Function() onSessionExpired;

  @override
  State<HomeTab> createState() => _HomeTabState();
}

class _HomeTabState extends State<HomeTab> with SingleTickerProviderStateMixin {
  Map<String, dynamic> _kpi = {};
  bool _loading = true;
  String? _err;
  late final AnimationController _stagger;

  static const _labels = <String, String>{
    'total': "Affectations aujourd'hui",
    'scheduled': 'Postes planifiés',
    'replaced': 'Remplacements effectués',
    'completed': 'Services terminés',
    'missed': 'Absences / manqués',
    'open_alerts': 'Alertes à traiter',
  };

  static const _icons = <String, IconData>{
    'total': Icons.calendar_month_rounded,
    'scheduled': Icons.schedule_rounded,
    'replaced': Icons.swap_horiz_rounded,
    'completed': Icons.task_alt_rounded,
    'missed': Icons.warning_amber_rounded,
    'open_alerts': Icons.notifications_active_rounded,
  };

  @override
  void initState() {
    super.initState();
    _stagger = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 620),
    );
    _load();
  }

  @override
  void dispose() {
    _stagger.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _err = null;
    });
    try {
      final s = await widget.api.fetchLiveStatus();
      if (mounted) setState(() => _kpi = s);
    } on AdminSessionExpiredException {
      await widget.onSessionExpired();
    } catch (_) {
      if (mounted) setState(() => _err = "Impossible de charger l'état. Tirez pour actualiser.");
    } finally {
      if (mounted) {
        setState(() => _loading = false);
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted && _err == null) _stagger.forward(from: 0);
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      color: CobraAdminColors.indigo,
      onRefresh: () async {
        await _load();
        widget.onRefreshAll();
      },
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 100),
        children: [
          Text(
            "Vue d'ensemble",
            style: GoogleFonts.outfit(
              fontSize: 22,
              fontWeight: FontWeight.w800,
              color: CobraAdminColors.ink,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            "Indicateurs du jour — alignés sur le tableau de bord web.",
            style: GoogleFonts.outfit(
              color: const Color(0xFF64748B),
              fontSize: 13,
            ),
          ),
          const SizedBox(height: 20),
          if (_loading)
            const AdminShimmerScope(child: KpiSkeletonList(count: 6))
          else if (_err != null)
            GlassPanel(
              child: Text(_err!, style: const TextStyle(color: CobraAdminColors.danger)),
            )
          else
            ..._kpi.entries.toList().asMap().entries.map((me) {
              final i = me.key;
              final e = me.value;
              final key = e.key;
              final label = _labels[key] ?? key;
              final raw = e.value;
              final value = raw is num ? raw.toString() : raw.toString();
              return cobraStaggerItem(
                controller: _stagger,
                index: i,
                child: Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: KpiTile(
                    label: label,
                    value: value,
                    icon: _icons[key],
                    accent: key == 'open_alerts'
                        ? CobraAdminColors.danger
                        : key == 'missed'
                            ? Colors.orange.shade700
                            : CobraAdminColors.indigo,
                  ),
                ),
              );
            }),
          const SizedBox(height: 16),
          GlassPanel(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(Icons.touch_app_rounded, color: CobraAdminColors.accent, size: 22),
                    const SizedBox(width: 8),
                    Text(
                      "Pilotage",
                      style: GoogleFonts.outfit(fontWeight: FontWeight.w800, fontSize: 16),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                Text(
                  "• Alertes : consultez et acquittez les retards / passations.\n"
                  "• Dépêcher : assignez un vigile remplaçant sur un poste du jour.\n"
                  "• Rapports : synthèse des pointages (retard, horaires).\n"
                  "• Équipe : liste des vigiles avec recherche rapide.",
                  style: GoogleFonts.outfit(
                    color: const Color(0xFF475569),
                    fontSize: 13,
                    height: 1.45,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          GlassPanel(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.language_rounded, color: CobraAdminColors.indigo.withAlpha(200), size: 22),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        "Administration complète sur le web",
                        style: GoogleFonts.outfit(
                          fontWeight: FontWeight.w800,
                          fontSize: 14,
                          color: CobraAdminColors.ink,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        "La création des sites, vigiles et affectations se fait depuis l’espace "
                        "« dashboard » navigateur. Cette app mobile couvre la supervision "
                        "opérationnelle en temps réel.",
                        style: GoogleFonts.outfit(
                          fontSize: 12,
                          height: 1.4,
                          color: const Color(0xFF64748B),
                        ),
                      ),
                    ],
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
