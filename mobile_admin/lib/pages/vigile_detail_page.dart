import 'dart:io';

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../services/admin_api.dart';
import '../theme/cobra_admin_theme.dart';
import 'portrait_capture_page.dart';

class VigileDetailPage extends StatefulWidget {
  const VigileDetailPage({
    super.key,
    required this.api,
    required this.vigileId,
    required this.onSessionExpired,
  });

  final AdminApi api;
  final int vigileId;
  final Future<void> Function() onSessionExpired;

  @override
  State<VigileDetailPage> createState() => _VigileDetailPageState();
}

class _VigileDetailPageState extends State<VigileDetailPage> {
  final _formKey = GlobalKey<FormState>();
  Map<String, dynamic>? _data;
  bool _loading = true;
  bool _saving = false;
  String? _newPhotoPath;

  late final TextEditingController _username;
  late final TextEditingController _first;
  late final TextEditingController _last;
  late final TextEditingController _email;
  late final TextEditingController _phone;
  late final TextEditingController _domicile;
  late final TextEditingController _aval;
  bool _isActive = true;
  bool _onDuty = false;

  @override
  void initState() {
    super.initState();
    _username = TextEditingController();
    _first = TextEditingController();
    _last = TextEditingController();
    _email = TextEditingController();
    _phone = TextEditingController();
    _domicile = TextEditingController();
    _aval = TextEditingController();
    _load();
  }

  @override
  void dispose() {
    _username.dispose();
    _first.dispose();
    _last.dispose();
    _email.dispose();
    _phone.dispose();
    _domicile.dispose();
    _aval.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final d = await widget.api.fetchVigile(widget.vigileId);
      if (!mounted) return;
      _applyData(d);
      setState(() => _data = d);
    } on AdminSessionExpiredException {
      await widget.onSessionExpired();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Impossible de charger la fiche vigile.')),
        );
        Navigator.of(context).pop();
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _applyData(Map<String, dynamic> d) {
    _username.text = (d['username'] ?? '').toString();
    _first.text = (d['first_name'] ?? '').toString();
    _last.text = (d['last_name'] ?? '').toString();
    _email.text = (d['email'] ?? '').toString();
    _phone.text = (d['phone_number'] ?? '').toString();
    _domicile.text = (d['domicile'] ?? '').toString();
    _aval.text = (d['aval'] ?? '').toString();
    _isActive = d['is_active'] == true;
    _onDuty = d['is_active_on_duty'] == true;
  }

  Future<void> _capturePortrait() async {
    final path = await PortraitCapturePage.capture(context);
    if (path != null && mounted) setState(() => _newPhotoPath = path);
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      final fields = <String, String>{
        'username': _username.text.trim(),
        'first_name': _first.text.trim(),
        'last_name': _last.text.trim(),
        'email': _email.text.trim(),
        'phone_number': _phone.text.trim(),
        'domicile': _domicile.text.trim(),
        'aval': _aval.text.trim(),
        'is_active': _isActive ? 'true' : 'false',
        'is_active_on_duty': _onDuty ? 'true' : 'false',
      };
      final updated = await widget.api.updateVigileMultipart(
        vigileId: widget.vigileId,
        fields: fields,
        photoPath: _newPhotoPath,
      );
      if (!mounted) return;
      setState(() {
        _data = updated;
        _newPhotoPath = null;
      });
      _applyData(updated);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Fiche vigile enregistrée.')),
      );
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

  Widget _faceChip() {
    final hasPhoto = _data?['profile_photo'] != null;
    final ok = _data?['face_enrollment_ok'] == true;
    late final String label;
    late final Color bg;
    late final Color fg;
    if (!hasPhoto) {
      label = 'Sans photo';
      bg = const Color(0xFFF1F5F9);
      fg = const Color(0xFF64748B);
    } else if (ok) {
      label = 'Empreinte OK';
      bg = const Color(0xFFDCFCE7);
      fg = const Color(0xFF166534);
    } else {
      label = 'Photo invalide';
      bg = const Color(0xFFFEE2E2);
      fg = const Color(0xFF991B1B);
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(999)),
      child: Text(
        label,
        style: GoogleFonts.outfit(fontSize: 11, fontWeight: FontWeight.w700, color: fg),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final photoUrl = _newPhotoPath != null
        ? null
        : widget.api.resolveMediaUrl(_data?['profile_photo']?.toString());

    return Scaffold(
      backgroundColor: CobraAdminColors.surface,
      appBar: AppBar(
        title: Text(
          _data?['display_name']?.toString() ?? 'Fiche vigile',
          style: GoogleFonts.outfit(fontWeight: FontWeight.w800),
        ),
        backgroundColor: CobraAdminColors.surface,
        foregroundColor: CobraAdminColors.ink,
        elevation: 0,
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : Form(
              key: _formKey,
              child: ListView(
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
                children: [
                  Center(
                    child: Column(
                      children: [
                        CircleAvatar(
                          radius: 52,
                          backgroundColor: CobraAdminColors.indigo.withAlpha(40),
                          backgroundImage: _newPhotoPath != null
                              ? FileImage(File(_newPhotoPath!))
                              : (photoUrl != null ? NetworkImage(photoUrl) : null),
                          child: (_newPhotoPath == null && photoUrl == null)
                              ? Icon(Icons.person, size: 48, color: CobraAdminColors.indigo)
                              : null,
                        ),
                        const SizedBox(height: 8),
                        _faceChip(),
                        const SizedBox(height: 12),
                        OutlinedButton.icon(
                          onPressed: _capturePortrait,
                          icon: const Icon(Icons.camera_alt_outlined, size: 18),
                          label: const Text('Reprendre le portrait'),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),
                  TextFormField(
                    controller: _username,
                    decoration: _dec('Identifiant'),
                    validator: (v) =>
                        (v == null || v.trim().isEmpty) ? 'Obligatoire' : null,
                  ),
                  const SizedBox(height: 12),
                  TextFormField(controller: _first, decoration: _dec('Prénom')),
                  const SizedBox(height: 12),
                  TextFormField(controller: _last, decoration: _dec('Nom')),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _email,
                    decoration: _dec('E-mail'),
                    keyboardType: TextInputType.emailAddress,
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _phone,
                    decoration: _dec('Téléphone'),
                    keyboardType: TextInputType.phone,
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _domicile,
                    decoration: _dec('Domicile'),
                    maxLines: 2,
                  ),
                  const SizedBox(height: 12),
                  TextFormField(controller: _aval, decoration: _dec('Aval')),
                  const SizedBox(height: 12),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Compte actif'),
                    subtitle: const Text('Autorise la connexion faciale'),
                    value: _isActive,
                    onChanged: (v) => setState(() => _isActive = v),
                  ),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Marqué en service'),
                    value: _onDuty,
                    onChanged: (v) => setState(() => _onDuty = v),
                  ),
                  const SizedBox(height: 20),
                  FilledButton(
                    onPressed: _saving ? null : _save,
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
                            'Enregistrer',
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
