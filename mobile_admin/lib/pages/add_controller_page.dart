import 'dart:io';

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:image_picker/image_picker.dart';

import '../services/admin_api.dart';
import '../theme/cobra_admin_theme.dart';
import '../widgets/glass_panel.dart';
import 'portrait_capture_page.dart';

class AddControllerPage extends StatefulWidget {
  const AddControllerPage({
    super.key,
    required this.api,
    required this.onSessionExpired,
    required this.sites,
  });

  final AdminApi api;
  final Future<void> Function() onSessionExpired;
  final List<Map<String, dynamic>> sites;

  @override
  State<AddControllerPage> createState() => _AddControllerPageState();
}

class _AddControllerPageState extends State<AddControllerPage> {
  final _formKey = GlobalKey<FormState>();
  final _username = TextEditingController();
  final _first = TextEditingController();
  final _last = TextEditingController();
  final _email = TextEditingController();
  final _phone = TextEditingController();
  String? _photoPath;
  final Set<int> _selectedSiteIds = {};
  bool _saving = false;

  List<Map<String, dynamic>> get _activeSites => widget.sites
      .where((s) => s['is_active'] == true || s['is_active'] == 1)
      .toList()
    ..sort(
      (a, b) => (a['name'] ?? '').toString().compareTo((b['name'] ?? '').toString()),
    );

  @override
  void dispose() {
    _username.dispose();
    _first.dispose();
    _last.dispose();
    _email.dispose();
    _phone.dispose();
    super.dispose();
  }

  Future<void> _capturePortrait() async {
    final path = await PortraitCapturePage.capture(context);
    if (path != null && mounted) setState(() => _photoPath = path);
  }

  Future<void> _pickFromGallery() async {
    final x = await ImagePicker().pickImage(
      source: ImageSource.gallery,
      maxWidth: 1600,
      imageQuality: 88,
    );
    if (x != null && mounted) setState(() => _photoPath = x.path);
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    if (_photoPath == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('La photo portrait est obligatoire (caméra guidée).'),
        ),
      );
      return;
    }
    if (!File(_photoPath!).existsSync()) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Fichier photo introuvable.')),
      );
      return;
    }

    setState(() => _saving = true);
    try {
      await widget.api.createControllerMultipart(
        photoPath: _photoPath!,
        username: _username.text.trim().isEmpty ? null : _username.text.trim(),
        firstName: _first.text,
        lastName: _last.text,
        email: _email.text,
        phoneNumber: _phone.text,
        siteIds: _selectedSiteIds.toList(),
      );
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
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: CobraAdminColors.surface,
      appBar: AppBar(
        title: Text(
          'Nouveau contrôleur',
          style: GoogleFonts.outfit(fontWeight: FontWeight.w800),
        ),
        backgroundColor: CobraAdminColors.surface,
        foregroundColor: CobraAdminColors.ink,
        elevation: 0,
      ),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
          children: [
            Text(
              'Identifiant laissé vide : généré automatiquement (CTR-xxx). '
              'Portrait vérifié côté serveur pour la reconnaissance faciale sur site.',
              style: GoogleFonts.outfit(fontSize: 13, color: const Color(0xFF64748B)),
            ),
            const SizedBox(height: 16),
            Text(
              'Photo portrait — caméra',
              style: GoogleFonts.outfit(
                fontWeight: FontWeight.w800,
                fontSize: 15,
                color: CobraAdminColors.ink,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              'Une seule personne, visage de face, bien éclairé, sans chapeau ni masque.',
              style: GoogleFonts.outfit(fontSize: 12, color: const Color(0xFF64748B)),
            ),
            const SizedBox(height: 12),
            Center(
              child: Column(
                children: [
                  GestureDetector(
                    onTap: _capturePortrait,
                    child: CircleAvatar(
                      radius: 48,
                      backgroundColor: CobraAdminColors.indigo.withAlpha(40),
                      backgroundImage:
                          _photoPath != null ? FileImage(File(_photoPath!)) : null,
                      child: _photoPath == null
                          ? Icon(
                              Icons.add_a_photo_rounded,
                              size: 36,
                              color: CobraAdminColors.indigo,
                            )
                          : null,
                    ),
                  ),
                  const SizedBox(height: 8),
                  FilledButton.icon(
                    onPressed: _capturePortrait,
                    style: FilledButton.styleFrom(
                      backgroundColor: CobraAdminColors.indigo,
                    ),
                    icon: const Icon(Icons.camera_alt_rounded, size: 20),
                    label: const Text('Prendre le portrait'),
                  ),
                  TextButton.icon(
                    onPressed: _pickFromGallery,
                    icon: const Icon(Icons.photo_library_outlined, size: 20),
                    label: const Text('Galerie (secours)'),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _username,
              decoration: _dec('Identifiant (généré automatiquement)', hint: 'CTR-xxx si vide'),
              style: GoogleFonts.outfit(),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _first,
              decoration: _dec('Prénom'),
              style: GoogleFonts.outfit(),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _last,
              decoration: _dec('Nom'),
              style: GoogleFonts.outfit(),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _email,
              decoration: _dec('Courriel'),
              keyboardType: TextInputType.emailAddress,
              style: GoogleFonts.outfit(),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _phone,
              decoration: _dec('Téléphone'),
              keyboardType: TextInputType.phone,
              style: GoogleFonts.outfit(),
            ),
            const SizedBox(height: 20),
            GlassPanel(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    'Sites autorisés',
                    style: GoogleFonts.outfit(
                      fontWeight: FontWeight.w800,
                      fontSize: 15,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Cochez les sites où ce contrôleur peut enregistrer son passage.',
                    style: GoogleFonts.outfit(fontSize: 12, color: const Color(0xFF64748B)),
                  ),
                  const SizedBox(height: 12),
                  if (_activeSites.isEmpty)
                    Text(
                      'Aucun site actif. Créez un site d\'abord.',
                      style: GoogleFonts.outfit(color: const Color(0xFF64748B)),
                    )
                  else
                    ..._activeSites.map((site) {
                      final id = (site['id'] as num?)?.toInt();
                      if (id == null) return const SizedBox.shrink();
                      final name = (site['name'] ?? 'Site').toString();
                      return CheckboxListTile(
                        contentPadding: EdgeInsets.zero,
                        value: _selectedSiteIds.contains(id),
                        title: Text(name, style: GoogleFonts.outfit(fontWeight: FontWeight.w600)),
                        subtitle: site['address'] != null
                            ? Text(
                                site['address'].toString(),
                                style: GoogleFonts.outfit(
                                  fontSize: 11,
                                  color: const Color(0xFF64748B),
                                ),
                              )
                            : null,
                        activeColor: CobraAdminColors.indigo,
                        onChanged: (checked) {
                          setState(() {
                            if (checked == true) {
                              _selectedSiteIds.add(id);
                            } else {
                              _selectedSiteIds.remove(id);
                            }
                          });
                        },
                      );
                    }),
                ],
              ),
            ),
            const SizedBox(height: 24),
            FilledButton(
              onPressed: _saving ? null : _submit,
              style: FilledButton.styleFrom(
                backgroundColor: CobraAdminColors.indigo,
                padding: const EdgeInsets.symmetric(vertical: 16),
              ),
              child: _saving
                  ? const SizedBox(
                      height: 22,
                      width: 22,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : Text(
                      'Créer le contrôleur',
                      style: GoogleFonts.outfit(fontWeight: FontWeight.w800),
                    ),
            ),
          ],
        ),
      ),
    );
  }

  InputDecoration _dec(String label, {String? hint}) {
    return InputDecoration(
      labelText: label,
      hintText: hint,
      labelStyle: GoogleFonts.outfit(color: const Color(0xFF64748B)),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
    );
  }
}
