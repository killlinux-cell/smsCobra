import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../models/admin_profile.dart';
import '../services/admin_api.dart';
import '../theme/cobra_admin_theme.dart';
import '../widgets/admin_shell_header.dart';
import '../widgets/cobra_background.dart';
import 'alerts_tab.dart';
import 'dispatch_tab.dart';
import 'home_tab.dart';
import 'login_page.dart';
import 'reports_tab.dart';
import 'gestion_tab.dart';

class AdminShell extends StatefulWidget {
  const AdminShell({super.key, required this.api, required this.firebaseConfigured});

  final AdminApi api;
  final bool firebaseConfigured;

  @override
  State<AdminShell> createState() => _AdminShellState();
}

class _AdminShellState extends State<AdminShell> with SingleTickerProviderStateMixin {
  int _index = 0;
  int _homeRemountKey = 0;
  String? _pushBanner;

  AdminProfile? _profile;
  bool _profileLoading = true;
  bool _profileFailed = false;

  late final AnimationController _pulseCtrl;
  late final Animation<double> _pulse;

  @override
  void initState() {
    super.initState();
    _pulseCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1700),
    )..repeat(reverse: true);
    _pulse = Tween<double>(begin: 0.88, end: 1.0).animate(
      CurvedAnimation(parent: _pulseCtrl, curve: Curves.easeInOut),
    );
    _loadProfile();
    _syncFcm();
  }

  @override
  void dispose() {
    _pulseCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadProfile() async {
    if (_profile == null) {
      setState(() {
        _profileLoading = true;
        _profileFailed = false;
      });
    }
    try {
      final p = await widget.api.fetchMe();
      if (mounted) {
        setState(() {
          _profile = p;
          _profileLoading = false;
          _profileFailed = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _profileLoading = false;
          _profileFailed = true;
        });
      }
    }
  }

  Future<void> _syncFcm() async {
    if (!widget.firebaseConfigured) {
      setState(() => _pushBanner = 'Push : configurez Firebase (google-services.json).');
      return;
    }
    try {
      final perm = await FirebaseMessaging.instance.requestPermission();
      if (perm.authorizationStatus == AuthorizationStatus.denied) {
        setState(() => _pushBanner = 'Notifications refusées dans les paramètres du téléphone.');
        return;
      }
      final token = await FirebaseMessaging.instance.getToken();
      if (token != null && token.isNotEmpty) {
        await widget.api.registerFcmToken(token);
        setState(() => _pushBanner = 'Notifications : token enregistré — vous recevrez les alertes ici.');
      }
    } on AdminSessionExpiredException {
      await _sessionExpired();
    } catch (_) {
      setState(() => _pushBanner = 'Push : enregistrement impossible (vérifiez la connexion).');
    }
  }

  void _refreshAll() {
    setState(() => _homeRemountKey++);
    _loadProfile();
  }

  Future<void> _logout() async {
    await widget.api.logout();
    if (!mounted) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute<void>(
        builder: (_) => LoginPage(
          api: widget.api,
          firebaseConfigured: widget.firebaseConfigured,
        ),
      ),
    );
  }

  Future<void> _sessionExpired() async {
    await widget.api.logout();
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Session expirée. Reconnectez-vous.')),
    );
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute<void>(
        builder: (_) => LoginPage(
          api: widget.api,
          firebaseConfigured: widget.firebaseConfigured,
        ),
      ),
      (_) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    final pages = <Widget>[
      HomeTab(
        key: ValueKey(_homeRemountKey),
        api: widget.api,
        onRefreshAll: _refreshAll,
        onSessionExpired: _sessionExpired,
      ),
      AlertsTab(api: widget.api, onSessionExpired: _sessionExpired),
      DispatchTab(api: widget.api, onSessionExpired: _sessionExpired),
      ReportsTab(api: widget.api, onSessionExpired: _sessionExpired),
      GestionTab(api: widget.api, onSessionExpired: _sessionExpired),
    ];

    return Scaffold(
      backgroundColor: CobraAdminColors.surface,
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          AdminBrandHeader(
            onSync: _refreshAll,
            onLogout: _logout,
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 0),
            child: Transform.translate(
              offset: const Offset(0, -14),
              child: AdminProfileCard(
                profile: _profile,
                pulse: _pulse,
                photoUrl: widget.api.resolveMediaUrl(_profile?.profilePhotoPath),
                loading: _profileLoading,
                loadFailed: _profileFailed,
              ),
            ),
          ),
          if (_pushBanner != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 6),
              child: Material(
                color: CobraAdminColors.indigo.withAlpha(25),
                borderRadius: BorderRadius.circular(12),
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  child: Row(
                    children: [
                      const Icon(Icons.info_outline_rounded, size: 18, color: CobraAdminColors.indigo),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          _pushBanner!,
                          style: const TextStyle(fontSize: 12, color: CobraAdminColors.ink),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          Expanded(
            child: CobraAdminBackground(
              child: pages[_index],
            ),
          ),
        ],
      ),
      bottomNavigationBar: NavigationBarTheme(
        data: NavigationBarThemeData(
          indicatorColor: CobraAdminColors.indigo.withAlpha(45),
          labelTextStyle: WidgetStateProperty.resolveWith((s) {
            if (s.contains(WidgetState.selected)) {
              return GoogleFonts.outfit(
                fontSize: 12,
                fontWeight: FontWeight.w700,
                color: CobraAdminColors.indigo,
              );
            }
            return GoogleFonts.outfit(fontSize: 12, color: const Color(0xFF64748B));
          }),
        ),
        child: NavigationBar(
          selectedIndex: _index,
          onDestinationSelected: (i) => setState(() => _index = i),
          destinations: const [
            NavigationDestination(
              icon: Icon(Icons.dashboard_outlined),
              selectedIcon: Icon(Icons.dashboard_rounded),
              label: 'Accueil',
            ),
            NavigationDestination(
              icon: Icon(Icons.notifications_outlined),
              selectedIcon: Icon(Icons.notifications_active_rounded),
              label: 'Alertes',
            ),
            NavigationDestination(
              icon: Icon(Icons.swap_horiz_outlined),
              selectedIcon: Icon(Icons.swap_horiz_rounded),
              label: 'Dépêcher',
            ),
            NavigationDestination(
              icon: Icon(Icons.description_outlined),
              selectedIcon: Icon(Icons.description_rounded),
              label: 'Rapports',
            ),
            NavigationDestination(
              icon: Icon(Icons.manage_accounts_outlined),
              selectedIcon: Icon(Icons.manage_accounts_rounded),
              label: 'Gestion',
            ),
          ],
        ),
      ),
    );
  }
}
