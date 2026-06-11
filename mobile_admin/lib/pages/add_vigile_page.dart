import 'dart:io';

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:image_picker/image_picker.dart';

import '../models/education_levels.dart';
import '../services/admin_api.dart';
import '../theme/cobra_admin_theme.dart';
import 'portrait_capture_page.dart';

class AddVigilePage extends StatefulWidget {
  const AddVigilePage({
    super.key,
    required this.api,
    required this.onSessionExpired,
  });

  final AdminApi api;
  final Future<void> Function() onSessionExpired;

  @override
  State<AddVigilePage> createState() => _AddVigilePageState();
}

class _AddVigilePageState extends State<AddVigilePage> {
  final _formKey = GlobalKey<FormState>();
  final _username = TextEditingController();
  final _first = TextEditingController();
  final _last = TextEditingController();
  final _email = TextEditingController();
  final _phone = TextEditingController();
  final _domicile = TextEditingController();
  final _aval = TextEditingController();
  final _height = TextEditingController();
  String? _photoPath;
  String? _idRectoPath;
  String? _idVersoPath;
  DateTime? _dateIntegration;
  String _educationLevel = '';
  bool _saving = false;

  @override
  void dispose() {
    _username.dispose();
    _first.dispose();
    _last.dispose();
    _email.dispose();
    _phone.dispose();
    _domicile.dispose();
    _aval.dispose();
    _height.dispose();
    super.dispose();
  }

  String _isoDate(DateTime d) =>
      '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  String _displayDate(DateTime d) =>
      '${d.day.toString().padLeft(2, '0')}/${d.month.toString().padLeft(2, '0')}/${d.year}';

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

  Future<void> _pickIdImage({required bool verso}) async {
    final source = await showModalBottomSheet<ImageSource>(
      context: context,
      builder: (ctx) => SafeArea(
        child: Wrap(
          children: [
            ListTile(
              leading: const Icon(Icons.camera_alt_outlined),
              title: const Text('Caméra arrière'),
              onTap: () => Navigator.pop(ctx, ImageSource.camera),
            ),
            ListTile(
              leading: const Icon(Icons.photo_library_outlined),
              title: const Text('Galerie / fichier'),
              onTap: () => Navigator.pop(ctx, ImageSource.gallery),
            ),
          ],
        ),
      ),
    );
    if (source == null || !mounted) return;
    final x = await ImagePicker().pickImage(
      source: source,
      maxWidth: 2000,
      imageQuality: 90,
    );
    if (x != null && mounted) {
      setState(() {
        if (verso) {
          _idVersoPath = x.path;
        } else {
          _idRectoPath = x.path;
        }
      });
    }
  }

  Future<void> _pickIntegrationDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _dateIntegration ?? DateTime.now(),
      firstDate: DateTime(2000),
      lastDate: DateTime.now().add(const Duration(days: 365)),
    );
    if (picked != null && mounted) setState(() => _dateIntegration = picked);
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
      await widget.api.createVigileMultipart(
        photoPath: _photoPath!,
        username: _username.text.trim().isEmpty ? null : _username.text.trim(),
        firstName: _first.text,
        lastName: _last.text,
        email: _email.text,
        phoneNumber: _phone.text,
        domicile: _domicile.text.trim().isEmpty ? null : _domicile.text.trim(),
        aval: _aval.text.trim().isEmpty ? null : _aval.text.trim(),
        dateIntegration:
            _dateIntegration != null ? _isoDate(_dateIntegration!) : null,
        heightCm: _height.text.trim().isEmpty ? null : _height.text.trim(),
        educationLevel:
            _educationLevel.isEmpty ? null : _educationLevel,
        idDocumentPath: _idRectoPath,
        idDocumentVersoPath: _idVersoPath,
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

  Widget _sectionTitle(String title, {String? subtitle}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8, top: 4),
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
          if (subtitle != null)
            Text(
              subtitle,
              style: GoogleFonts.outfit(fontSize: 12, color: const Color(0xFF64748B)),
            ),
        ],
      ),
    );
  }

  Widget _fileChip(String label, String? path, VoidCallback onPick) {
    return OutlinedButton.icon(
      onPressed: onPick,
      icon: Icon(
        path != null ? Icons.check_circle_outline : Icons.upload_file_outlined,
        color: path != null ? const Color(0xFF16A34A) : CobraAdminColors.indigo,
      ),
      label: Text(
        path != null ? '$label — fichier OK' : label,
        style: GoogleFonts.outfit(fontWeight: FontWeight.w600),
      ),
      style: OutlinedButton.styleFrom(
        padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 12),
        alignment: Alignment.centerLeft,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: CobraAdminColors.surface,
      appBar: AppBar(
        title: Text(
          'Nouveau vigile',
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
              'Identifiant laissé vide : généré automatiquement (VIR-xxx). '
              'Portrait vérifié côté serveur comme sur le web.',
              style: GoogleFonts.outfit(fontSize: 13, color: const Color(0xFF64748B)),
            ),
            const SizedBox(height: 16),
            _sectionTitle(
              'Photo portrait — caméra',
              subtitle: 'Visage seul, de face, bien éclairé.',
            ),
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
              decoration: _dec(
                'Identifiant (généré automatiquement)',
                hint: 'VIR-xxx si vide',
              ),
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
            const SizedBox(height: 12),
            TextFormField(
              controller: _domicile,
              decoration: _dec('Domicile', hint: 'Adresse complète, quartier, ville…'),
              keyboardType: TextInputType.streetAddress,
              maxLines: 3,
              style: GoogleFonts.outfit(),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _aval,
              decoration: _dec('Aval', hint: 'Référence ou mention interne'),
              style: GoogleFonts.outfit(),
            ),
            const SizedBox(height: 12),
            _sectionTitle("Date d'intégration"),
            OutlinedButton.icon(
              onPressed: _pickIntegrationDate,
              icon: const Icon(Icons.calendar_today_outlined, size: 18),
              label: Text(
                _dateIntegration != null
                    ? _displayDate(_dateIntegration!)
                    : 'Choisir une date (optionnel)',
                style: GoogleFonts.outfit(fontWeight: FontWeight.w600),
              ),
              style: OutlinedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 16),
              ),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _height,
              decoration: _dec('Taille (cm)', hint: 'ex. 175'),
              keyboardType: TextInputType.number,
              validator: (v) {
                final t = v?.trim() ?? '';
                if (t.isEmpty) return null;
                final n = int.tryParse(t);
                if (n == null || n < 100 || n > 250) {
                  return 'Entre 100 et 250 cm';
                }
                return null;
              },
              style: GoogleFonts.outfit(),
            ),
            const SizedBox(height: 12),
            InputDecorator(
              decoration: _dec("Niveau d'études"),
              child: DropdownButtonHideUnderline(
                child: DropdownButton<String>(
                  isExpanded: true,
                  value: _educationLevel,
                  items: kEducationLevels
                      .map(
                        (o) => DropdownMenuItem(
                          value: o.value,
                          child: Text(o.label, style: GoogleFonts.outfit()),
                        ),
                      )
                      .toList(),
                  onChanged: (v) => setState(() => _educationLevel = v ?? ''),
                ),
              ),
            ),
            const SizedBox(height: 20),
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                border: Border.all(color: const Color(0xFFE2E8F0)),
                borderRadius: BorderRadius.circular(14),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _sectionTitle(
                    "Carte d'identité",
                    subtitle: 'Recto et verso — caméra ou galerie (optionnel).',
                  ),
                  _fileChip(
                    'Recto (face avant)',
                    _idRectoPath,
                    () => _pickIdImage(verso: false),
                  ),
                  const SizedBox(height: 8),
                  _fileChip(
                    'Verso (face arrière)',
                    _idVersoPath,
                    () => _pickIdImage(verso: true),
                  ),
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
                      'Créer le vigile',
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
