import 'dart:io';

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:image_picker/image_picker.dart';

import '../services/admin_api.dart';
import '../theme/cobra_admin_theme.dart';

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
  String? _photoPath;
  bool _saving = false;

  @override
  void dispose() {
    _username.dispose();
    _first.dispose();
    _last.dispose();
    _email.dispose();
    _phone.dispose();
    _domicile.dispose();
    super.dispose();
  }

  Future<void> _pickPhoto() async {
    final picker = ImagePicker();
    final x = await picker.pickImage(
      source: ImageSource.gallery,
      maxWidth: 1600,
      imageQuality: 88,
    );
    if (x != null && mounted) {
      setState(() => _photoPath = x.path);
    }
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    if (_photoPath == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('La photo de profil est obligatoire.')),
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
        username: _username.text.trim().isEmpty ? null : _username.text.trim(),
        firstName: _first.text,
        lastName: _last.text,
        email: _email.text,
        phoneNumber: _phone.text,
        domicile: _domicile.text.trim().isEmpty ? null : _domicile.text.trim(),
        photoPath: _photoPath!,
      );
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } on AdminSessionExpiredException {
      await widget.onSessionExpired();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(e.toString())),
        );
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
              "Identifiant laissé vide : généré automatiquement (VIR-xxx). Connexion vigile par visage.",
              style: GoogleFonts.outfit(
                fontSize: 13,
                color: const Color(0xFF64748B),
              ),
            ),
            const SizedBox(height: 16),
            Center(
              child: Column(
                children: [
                  GestureDetector(
                    onTap: _pickPhoto,
                    child: CircleAvatar(
                      radius: 48,
                      backgroundColor: CobraAdminColors.indigo.withAlpha(40),
                      backgroundImage: _photoPath != null
                          ? FileImage(File(_photoPath!))
                          : null,
                      child: _photoPath == null
                          ? Icon(
                              Icons.add_a_photo_rounded,
                              size: 36,
                              color: CobraAdminColors.indigo,
                            )
                          : null,
                    ),
                  ),
                  TextButton.icon(
                    onPressed: _pickPhoto,
                    icon: const Icon(Icons.photo_library_outlined, size: 20),
                    label: const Text('Choisir une photo'),
                  ),
                ],
              ),
            ),
            TextFormField(
              controller: _username,
              decoration: _dec('Identifiant (optionnel)'),
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
              decoration: _dec('E-mail'),
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
              decoration: _dec('Domicile'),
              keyboardType: TextInputType.streetAddress,
              maxLines: 3,
              style: GoogleFonts.outfit(),
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

  InputDecoration _dec(String label) {
    return InputDecoration(
      labelText: label,
      labelStyle: GoogleFonts.outfit(color: const Color(0xFF64748B)),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
    );
  }
}
