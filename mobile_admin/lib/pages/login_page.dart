import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../services/admin_api.dart';
import '../theme/cobra_admin_theme.dart';
import 'admin_shell.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key, required this.api, required this.firebaseConfigured});

  final AdminApi api;
  final bool firebaseConfigured;

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _user = TextEditingController();
  final _pass = TextEditingController();
  bool _busy = false;
  String? _error;

  Future<void> _login() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.api.login(_user.text.trim(), _pass.text);
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(
          builder: (_) => AdminShell(
            api: widget.api,
            firebaseConfigured: widget.firebaseConfigured,
          ),
        ),
      );
    } catch (_) {
      setState(() => _error = "Connexion impossible. Utilisez un compte administrateur.");
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        width: double.infinity,
        height: double.infinity,
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: CobraAdminColors.headerGradient,
          ),
        ),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 400),
                child: Column(
                  children: [
                    const SizedBox(height: 12),
                    Image.asset(
                      'assets/images/sms_logo.png',
                      height: 88,
                      fit: BoxFit.contain,
                    ),
                    const SizedBox(height: 16),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                      decoration: BoxDecoration(
                        color: Colors.black.withAlpha(40),
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: Text(
                        "Supervision mobile",
                        style: GoogleFonts.outfit(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: Colors.white,
                          letterSpacing: 0.5,
                        ),
                      ),
                    ),
                    const SizedBox(height: 28),
                    Material(
                      elevation: 16,
                      shadowColor: Colors.black.withAlpha(80),
                      borderRadius: BorderRadius.circular(24),
                      color: Colors.white,
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(22, 26, 22, 22),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            Text(
                              "Connexion",
                              style: GoogleFonts.outfit(
                                fontSize: 22,
                                fontWeight: FontWeight.w800,
                                color: CobraAdminColors.ink,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              "Compte superviseur, admin société ou super admin.",
                              style: GoogleFonts.outfit(
                                fontSize: 13,
                                color: const Color(0xFF64748B),
                              ),
                            ),
                            if (!widget.firebaseConfigured) ...[
                              const SizedBox(height: 14),
                              Container(
                                padding: const EdgeInsets.all(10),
                                decoration: BoxDecoration(
                                  color: Colors.orange.shade50,
                                  borderRadius: BorderRadius.circular(12),
                                  border: Border.all(color: Colors.orange.shade200),
                                ),
                                child: Text(
                                  "Notifications : ajoutez google-services.json (voir FCM_SETUP.txt). Le reste de l’app fonctionne.",
                                  textAlign: TextAlign.center,
                                  style: GoogleFonts.outfit(
                                    color: Colors.orange.shade900,
                                    fontSize: 12,
                                    height: 1.35,
                                  ),
                                ),
                              ),
                            ],
                            const SizedBox(height: 20),
                            TextField(
                              controller: _user,
                              style: GoogleFonts.outfit(),
                              decoration: InputDecoration(
                                labelText: "Identifiant",
                                filled: true,
                                fillColor: Color(0xFFF5F3FF),
                                border: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(14),
                                ),
                              ),
                            ),
                            const SizedBox(height: 12),
                            TextField(
                              controller: _pass,
                              obscureText: true,
                              style: GoogleFonts.outfit(),
                              decoration: InputDecoration(
                                labelText: "Mot de passe",
                                filled: true,
                                fillColor: Color(0xFFF5F3FF),
                                border: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(14),
                                ),
                              ),
                            ),
                            if (_error != null) ...[
                              const SizedBox(height: 12),
                              Text(
                                _error!,
                                style: GoogleFonts.outfit(
                                  color: CobraAdminColors.danger,
                                  fontSize: 13,
                                ),
                              ),
                            ],
                            const SizedBox(height: 22),
                            SizedBox(
                              height: 52,
                              child: FilledButton(
                                onPressed: _busy ? null : _login,
                                style: FilledButton.styleFrom(
                                  backgroundColor: CobraAdminColors.indigo,
                                  shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(14),
                                  ),
                                ),
                                child: Text(
                                  _busy ? "Connexion…" : "Se connecter",
                                  style: GoogleFonts.outfit(
                                    fontWeight: FontWeight.w700,
                                    fontSize: 16,
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
