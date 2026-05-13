import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../services/admin_api.dart';
import '../theme/cobra_admin_theme.dart';
import '../widgets/admin_shimmer.dart';
import '../widgets/cobra_stagger.dart';
import '../widgets/glass_panel.dart';
import 'add_edit_site_page.dart';
import 'add_vigile_page.dart';

/// Onglet Gestion : vigiles + sites (liste et création, édition site), aligné sur le dashboard web.
class GestionTab extends StatefulWidget {
  const GestionTab({super.key, required this.api, required this.onSessionExpired});

  final AdminApi api;
  final Future<void> Function() onSessionExpired;

  @override
  State<GestionTab> createState() => _GestionTabState();
}

class _GestionTabState extends State<GestionTab> with TickerProviderStateMixin {
  late final TabController _tabController;
  List<Map<String, dynamic>> _vigiles = [];
  List<Map<String, dynamic>> _sites = [];
  bool _loadingV = true;
  bool _loadingS = true;
  String _queryV = '';
  String _queryS = '';
  late final AnimationController _staggerV;
  late final AnimationController _staggerS;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _tabController.addListener(() {
      if (!_tabController.indexIsChanging) setState(() {});
    });
    _staggerV = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 680),
    );
    _staggerS = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 680),
    );
    _loadVigiles();
    _loadSites();
  }

  @override
  void dispose() {
    _tabController.dispose();
    _staggerV.dispose();
    _staggerS.dispose();
    super.dispose();
  }

  Future<void> _loadVigiles() async {
    setState(() => _loadingV = true);
    try {
      final raw = await widget.api.fetchVigiles();
      if (!mounted) return;
      final list = raw.map((e) => Map<String, dynamic>.from(e as Map)).toList();
      setState(() => _vigiles = list);
    } on AdminSessionExpiredException {
      await widget.onSessionExpired();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Impossible de charger les vigiles.')),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _loadingV = false);
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) _staggerV.forward(from: 0);
        });
      }
    }
  }

  Future<void> _loadSites() async {
    setState(() => _loadingS = true);
    try {
      final raw = await widget.api.fetchSites();
      if (!mounted) return;
      final list = raw.map((e) => Map<String, dynamic>.from(e as Map)).toList();
      setState(() => _sites = list);
    } on AdminSessionExpiredException {
      await widget.onSessionExpired();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Impossible de charger les sites.')),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _loadingS = false);
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) _staggerS.forward(from: 0);
        });
      }
    }
  }

  List<Map<String, dynamic>> get _filteredV {
    final q = _queryV.trim().toLowerCase();
    if (q.isEmpty) return _vigiles;
    return _vigiles.where((m) {
      final name = (m['display_name'] ?? '').toString().toLowerCase();
      final user = (m['username'] ?? '').toString().toLowerCase();
      return name.contains(q) || user.contains(q);
    }).toList();
  }

  List<Map<String, dynamic>> get _filteredS {
    final q = _queryS.trim().toLowerCase();
    if (q.isEmpty) return _sites;
    return _sites.where((m) {
      final name = (m['name'] ?? '').toString().toLowerCase();
      final addr = (m['address'] ?? '').toString().toLowerCase();
      return name.contains(q) || addr.contains(q);
    }).toList();
  }

  Future<void> _openAddVigile() async {
    final ok = await Navigator.of(context).push<bool>(
      MaterialPageRoute<bool>(
        builder: (_) => AddVigilePage(
          api: widget.api,
          onSessionExpired: widget.onSessionExpired,
        ),
      ),
    );
    if (ok == true) _loadVigiles();
  }

  Future<void> _openAddSite() async {
    final ok = await Navigator.of(context).push<bool>(
      MaterialPageRoute<bool>(
        builder: (_) => AddEditSitePage(
          api: widget.api,
          onSessionExpired: widget.onSessionExpired,
        ),
      ),
    );
    if (ok == true) _loadSites();
  }

  Future<void> _openEditSite(Map<String, dynamic> site) async {
    final ok = await Navigator.of(context).push<bool>(
      MaterialPageRoute<bool>(
        builder: (_) => AddEditSitePage(
          api: widget.api,
          onSessionExpired: widget.onSessionExpired,
          existing: site,
        ),
      ),
    );
    if (ok == true) _loadSites();
  }

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
              child: Text(
                'Gestion',
                style: GoogleFonts.outfit(
                  fontSize: 22,
                  fontWeight: FontWeight.w900,
                  color: CobraAdminColors.ink,
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
              child: Text(
                'Vigiles et sites — comme sur le tableau de bord web.',
                style: GoogleFonts.outfit(
                  color: const Color(0xFF64748B),
                  fontSize: 13,
                  height: 1.35,
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Material(
                color: Colors.white.withAlpha(242),
                borderRadius: BorderRadius.circular(14),
                child: TabBar(
                  controller: _tabController,
                  indicator: BoxDecoration(
                    color: CobraAdminColors.indigo.withAlpha(45),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  indicatorSize: TabBarIndicatorSize.tab,
                  labelColor: CobraAdminColors.indigo,
                  unselectedLabelColor: const Color(0xFF64748B),
                  labelStyle: GoogleFonts.outfit(fontWeight: FontWeight.w800, fontSize: 14),
                  unselectedLabelStyle: GoogleFonts.outfit(fontWeight: FontWeight.w600, fontSize: 14),
                  tabs: const [
                    Tab(text: 'Vigiles'),
                    Tab(text: 'Sites'),
                  ],
                ),
              ),
            ),
            Expanded(
              child: TabBarView(
                controller: _tabController,
                children: [
                  _buildVigilesBody(),
                  _buildSitesBody(),
                ],
              ),
            ),
          ],
        ),
        Positioned(
          right: 20,
          bottom: 24,
          child: FloatingActionButton.extended(
            onPressed: _tabController.index == 0 ? _openAddVigile : _openAddSite,
            backgroundColor: CobraAdminColors.indigo,
            icon: const Icon(Icons.add_rounded),
            label: Text(
              _tabController.index == 0 ? 'Vigile' : 'Site',
              style: GoogleFonts.outfit(fontWeight: FontWeight.w800),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildVigilesBody() {
    return RefreshIndicator(
      color: CobraAdminColors.indigo,
      onRefresh: _loadVigiles,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 100),
        children: [
          TextField(
            onChanged: (v) => setState(() => _queryV = v),
            decoration: _searchDec('Rechercher un vigile…'),
            style: GoogleFonts.outfit(fontSize: 15),
          ),
          const SizedBox(height: 16),
          if (_loadingV)
            const AdminShimmerScope(
              child: Column(
                children: [
                  ListRowSkeletonCard(),
                  ListRowSkeletonCard(),
                  ListRowSkeletonCard(),
                ],
              ),
            )
          else if (_filteredV.isEmpty)
            GlassPanel(
              child: Text(
                _vigiles.isEmpty
                    ? 'Aucun vigile. Appuyez sur le bouton pour en créer un.'
                    : 'Aucun résultat pour « $_queryV ».',
                style: GoogleFonts.outfit(color: const Color(0xFF64748B)),
              ),
            )
          else
            ..._filteredV.asMap().entries.map((e) {
              final i = e.key;
              final m = e.value;
              final name = (m['display_name'] ?? m['username'] ?? '—').toString();
              final user = (m['username'] ?? '').toString();
              final id = (m['id'] as num?)?.toInt() ?? 0;
              final photoUrl = widget.api.resolveMediaUrl(m['profile_photo']?.toString());
              final domicile = (m['domicile'] ?? '').toString().trim();
              return cobraStaggerItem(
                controller: _staggerV,
                index: i,
                child: Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: GlassPanel(
                    padding: const EdgeInsets.all(14),
                    child: Row(
                      children: [
                        CircleAvatar(
                          radius: 26,
                          backgroundColor: CobraAdminColors.indigo.withAlpha(40),
                          foregroundImage: photoUrl != null ? NetworkImage(photoUrl) : null,
                          child: photoUrl == null
                              ? Text(
                                  name.isNotEmpty ? name.characters.first.toUpperCase() : '?',
                                  style: GoogleFonts.outfit(fontWeight: FontWeight.w800),
                                )
                              : null,
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                name,
                                style: GoogleFonts.outfit(
                                  fontWeight: FontWeight.w800,
                                  fontSize: 16,
                                  color: CobraAdminColors.ink,
                                ),
                              ),
                              const SizedBox(height: 2),
                              Text(
                                '@$user · #$id',
                                style: GoogleFonts.outfit(
                                  fontSize: 12,
                                  color: const Color(0xFF64748B),
                                ),
                              ),
                              if (domicile.isNotEmpty) ...[
                                const SizedBox(height: 4),
                                Text(
                                  domicile,
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                  style: GoogleFonts.outfit(
                                    fontSize: 11,
                                    color: const Color(0xFF64748B),
                                    height: 1.25,
                                  ),
                                ),
                              ],
                            ],
                          ),
                        ),
                        Icon(
                          Icons.verified_user_outlined,
                          color: CobraAdminColors.accent.withAlpha(220),
                          size: 22,
                        ),
                      ],
                    ),
                  ),
                ),
              );
            }),
        ],
      ),
    );
  }

  Widget _buildSitesBody() {
    return RefreshIndicator(
      color: CobraAdminColors.indigo,
      onRefresh: _loadSites,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 100),
        children: [
          TextField(
            onChanged: (v) => setState(() => _queryS = v),
            decoration: _searchDec('Rechercher un site…'),
            style: GoogleFonts.outfit(fontSize: 15),
          ),
          const SizedBox(height: 16),
          if (_loadingS)
            const AdminShimmerScope(
              child: Column(
                children: [
                  ListRowSkeletonCard(),
                  ListRowSkeletonCard(),
                  ListRowSkeletonCard(),
                ],
              ),
            )
          else if (_filteredS.isEmpty)
            GlassPanel(
              child: Text(
                _sites.isEmpty
                    ? 'Aucun site. Appuyez sur le bouton pour en créer un.'
                    : 'Aucun résultat pour « $_queryS ».',
                style: GoogleFonts.outfit(color: const Color(0xFF64748B)),
              ),
            )
          else
            ..._filteredS.asMap().entries.map((e) {
              final i = e.key;
              final m = e.value;
              final name = (m['name'] ?? '—').toString();
              final addr = (m['address'] ?? '').toString();
              final active = m['is_active'] == true || m['is_active'] == 1;
              final radius = m['geofence_radius_meters'];
              return cobraStaggerItem(
                controller: _staggerS,
                index: i,
                child: Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: InkWell(
                    onTap: () => _openEditSite(m),
                    borderRadius: BorderRadius.circular(16),
                    child: GlassPanel(
                      padding: const EdgeInsets.all(14),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Container(
                            padding: const EdgeInsets.all(10),
                            decoration: BoxDecoration(
                              color: CobraAdminColors.indigo.withAlpha(35),
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Icon(
                              Icons.place_rounded,
                              color: CobraAdminColors.indigo,
                              size: 24,
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    Expanded(
                                      child: Text(
                                        name,
                                        style: GoogleFonts.outfit(
                                          fontWeight: FontWeight.w800,
                                          fontSize: 16,
                                          color: CobraAdminColors.ink,
                                        ),
                                      ),
                                    ),
                                    if (!active)
                                      Container(
                                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                        decoration: BoxDecoration(
                                          color: const Color(0xFFFEE2E2),
                                          borderRadius: BorderRadius.circular(8),
                                        ),
                                        child: Text(
                                          'Inactif',
                                          style: GoogleFonts.outfit(
                                            fontSize: 11,
                                            fontWeight: FontWeight.w700,
                                            color: const Color(0xFFB91C1C),
                                          ),
                                        ),
                                      ),
                                  ],
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  addr,
                                  style: GoogleFonts.outfit(
                                    fontSize: 13,
                                    color: const Color(0xFF64748B),
                                    height: 1.3,
                                  ),
                                ),
                                if (radius != null)
                                  Padding(
                                    padding: const EdgeInsets.only(top: 6),
                                    child: Text(
                                      'Géofence : $radius m — appuyez pour modifier',
                                      style: GoogleFonts.outfit(
                                        fontSize: 12,
                                        color: CobraAdminColors.indigo,
                                        fontWeight: FontWeight.w600,
                                      ),
                                    ),
                                  ),
                              ],
                            ),
                          ),
                          const Icon(Icons.chevron_right_rounded, color: Color(0xFF94A3B8)),
                        ],
                      ),
                    ),
                  ),
                ),
              );
            }),
        ],
      ),
    );
  }

  InputDecoration _searchDec(String hint) {
    return InputDecoration(
      hintText: hint,
      hintStyle: GoogleFonts.outfit(color: const Color(0xFF94A3B8), fontSize: 14),
      prefixIcon: const Icon(Icons.search_rounded, color: CobraAdminColors.indigo),
      filled: true,
      fillColor: Colors.white.withAlpha(242),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: Color(0xFFE2E8F0)),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: Color(0xFFE2E8F0)),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: CobraAdminColors.indigo, width: 1.5),
      ),
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
    );
  }
}
