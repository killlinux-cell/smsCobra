import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../services/admin_api.dart';
import '../theme/cobra_admin_theme.dart';
import '../widgets/glass_panel.dart';
import 'add_edit_site_page.dart';

class SiteDetailPage extends StatefulWidget {
  const SiteDetailPage({
    super.key,
    required this.api,
    required this.siteId,
    required this.onSessionExpired,
  });

  final AdminApi api;
  final int siteId;
  final Future<void> Function() onSessionExpired;

  @override
  State<SiteDetailPage> createState() => _SiteDetailPageState();
}

class _SiteDetailPageState extends State<SiteDetailPage> {
  Map<String, dynamic>? _data;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final d = await widget.api.fetchSite(widget.siteId);
      if (mounted) setState(() => _data = d);
    } on AdminSessionExpiredException {
      await widget.onSessionExpired();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Impossible de charger la fiche site.')),
        );
        Navigator.of(context).pop();
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  String _timeShort(dynamic t) {
    if (t == null) return '—';
    final s = t.toString();
    return s.length >= 5 ? s.substring(0, 5) : s;
  }

  String _formatCreatedAt(dynamic raw) {
    if (raw == null) return '—';
    final s = raw.toString();
    if (s.length >= 10) {
      final p = s.substring(0, 10).split('-');
      if (p.length == 3) return '${p[2]}/${p[1]}/${p[0]}';
    }
    return s;
  }

  Future<void> _openEdit() async {
    if (_data == null) return;
    final ok = await Navigator.of(context).push<bool>(
      MaterialPageRoute<bool>(
        builder: (_) => AddEditSitePage(
          api: widget.api,
          onSessionExpired: widget.onSessionExpired,
          existing: _data,
        ),
      ),
    );
    if (ok == true) _load();
  }

  Widget _row(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 130,
            child: Text(
              label,
              style: GoogleFonts.outfit(
                fontSize: 12,
                fontWeight: FontWeight.w700,
                color: const Color(0xFF64748B),
              ),
            ),
          ),
          Expanded(
            child: Text(
              value.isEmpty ? '—' : value,
              style: GoogleFonts.outfit(
                fontWeight: FontWeight.w600,
                color: CobraAdminColors.ink,
              ),
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final d = _data;
    final active = d?['is_active'] == true || d?['is_active'] == 1;

    return Scaffold(
      backgroundColor: CobraAdminColors.surface,
      appBar: AppBar(
        title: Text(
          d?['name']?.toString() ?? 'Fiche site',
          style: GoogleFonts.outfit(fontWeight: FontWeight.w800),
        ),
        backgroundColor: CobraAdminColors.surface,
        foregroundColor: CobraAdminColors.ink,
        elevation: 0,
        actions: [
          if (!_loading && d != null)
            IconButton(
              onPressed: _openEdit,
              icon: const Icon(Icons.edit_outlined),
              tooltip: 'Modifier',
            ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: CobraAdminColors.indigo))
          : d == null
              ? const SizedBox.shrink()
              : ListView(
                  padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
                  children: [
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                          decoration: BoxDecoration(
                            color: active
                                ? const Color(0xFFDCFCE7)
                                : const Color(0xFFF1F5F9),
                            borderRadius: BorderRadius.circular(999),
                          ),
                          child: Text(
                            active ? 'Actif' : 'Inactif',
                            style: GoogleFonts.outfit(
                              fontSize: 11,
                              fontWeight: FontWeight.w800,
                              color: active
                                  ? const Color(0xFF166534)
                                  : const Color(0xFF64748B),
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    GlassPanel(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Text(
                            'Informations générales',
                            style: GoogleFonts.outfit(
                              fontWeight: FontWeight.w800,
                              fontSize: 15,
                            ),
                          ),
                          const SizedBox(height: 12),
                          _row('Date de création', _formatCreatedAt(d['created_at'])),
                          _row('Adresse', (d['address'] ?? '').toString()),
                          _row(
                            'Responsable',
                            (d['site_manager_name'] ?? '').toString(),
                          ),
                          _row(
                            'Tél. responsable',
                            (d['site_manager_phone'] ?? '').toString(),
                          ),
                          _row(
                            'SMS site',
                            (d['site_sms_phone'] ?? '').toString(),
                          ),
                          _row('Fuseau', (d['timezone'] ?? 'Africa/Abidjan').toString()),
                        ],
                      ),
                    ),
                    const SizedBox(height: 12),
                    GlassPanel(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Text(
                            'Planning & effectifs',
                            style: GoogleFonts.outfit(
                              fontWeight: FontWeight.w800,
                              fontSize: 15,
                            ),
                          ),
                          const SizedBox(height: 12),
                          _row(
                            'Horaires attendus',
                            '${_timeShort(d['expected_start_time'])} – ${_timeShort(d['expected_end_time'])}',
                          ),
                          _row(
                            'Effectif cible',
                            'Jour : ${d['day_staff_required'] ?? 1} · Nuit : ${d['night_staff_required'] ?? 1}',
                          ),
                          _row(
                            'Tolérance retard',
                            '${d['late_tolerance_minutes'] ?? 15} min',
                          ),
                          _row(
                            'Alerte relève',
                            '${d['relief_late_alert_minutes'] ?? d['late_tolerance_minutes'] ?? 15} min',
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 12),
                    GlassPanel(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Text(
                            'Géofence',
                            style: GoogleFonts.outfit(
                              fontWeight: FontWeight.w800,
                              fontSize: 15,
                            ),
                          ),
                          const SizedBox(height: 12),
                          _row(
                            'Rayon',
                            '${d['geofence_radius_meters'] ?? 250} m (+ marge ${d['geofence_gps_margin_meters'] ?? 75} m)',
                          ),
                          if (d['latitude'] != null && d['longitude'] != null)
                            _row(
                              'Coordonnées',
                              'Lat. ${d['latitude']} · Long. ${d['longitude']}',
                            )
                          else
                            _row('Coordonnées', 'Non renseignées (géofence inactive)'),
                        ],
                      ),
                    ),
                    const SizedBox(height: 24),
                    FilledButton.icon(
                      onPressed: _openEdit,
                      style: FilledButton.styleFrom(
                        backgroundColor: CobraAdminColors.indigo,
                        padding: const EdgeInsets.symmetric(vertical: 16),
                      ),
                      icon: const Icon(Icons.edit_outlined),
                      label: Text(
                        'Modifier le site',
                        style: GoogleFonts.outfit(fontWeight: FontWeight.w800),
                      ),
                    ),
                  ],
                ),
    );
  }
}
