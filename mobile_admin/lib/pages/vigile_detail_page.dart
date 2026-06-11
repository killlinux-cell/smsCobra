import 'dart:io';

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:image_picker/image_picker.dart';

import '../models/education_levels.dart';
import '../services/admin_api.dart';
import '../theme/cobra_admin_theme.dart';
import '../widgets/glass_panel.dart';
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
  String? _newIdRectoPath;
  String? _newIdVersoPath;

  late final TextEditingController _username;
  late final TextEditingController _first;
  late final TextEditingController _last;
  late final TextEditingController _email;
  late final TextEditingController _phone;
  late final TextEditingController _domicile;
  late final TextEditingController _aval;
  late final TextEditingController _height;
  DateTime? _dateIntegration;
  String _educationLevel = '';
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
    _height = TextEditingController();
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
    _height.dispose();
    super.dispose();
  }

  String _isoDate(DateTime d) =>
      '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  String _displayDate(DateTime d) =>
      '${d.day.toString().padLeft(2, '0')}/${d.month.toString().padLeft(2, '0')}/${d.year}';

  String _formatDateTime(dynamic raw) {
    if (raw == null) return 'Jamais';
    final s = raw.toString();
    if (s.length >= 16) {
      final d = s.substring(0, 10).split('-');
      final t = s.substring(11, 16);
      if (d.length == 3) return '${d[2]}/${d[1]}/${d[0]} $t';
    }
    return s;
  }

  String _educationLabel(String? code) {
    for (final o in kEducationLevels) {
      if (o.value == (code ?? '')) return o.label;
    }
    return code == null || code.isEmpty ? '— Non renseigné —' : code;
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
    _height.text = d['height_cm']?.toString() ?? '';
    _educationLevel = (d['education_level'] ?? '').toString();
    _isActive = d['is_active'] == true;
    _onDuty = d['is_active_on_duty'] == true;
    final rawDate = d['date_integration']?.toString();
    if (rawDate != null && rawDate.length >= 10) {
      _dateIntegration = DateTime.tryParse(rawDate.substring(0, 10));
    } else {
      _dateIntegration = null;
    }
  }

  Future<void> _capturePortrait() async {
    final path = await PortraitCapturePage.capture(context);
    if (path != null && mounted) setState(() => _newPhotoPath = path);
  }

  Future<void> _pickId({required bool verso}) async {
    final x = await ImagePicker().pickImage(source: ImageSource.gallery, imageQuality: 90);
    if (x != null && mounted) {
      setState(() {
        if (verso) {
          _newIdVersoPath = x.path;
        } else {
          _newIdRectoPath = x.path;
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
        'education_level': _educationLevel,
      };
      if (_height.text.trim().isNotEmpty) {
        fields['height_cm'] = _height.text.trim();
      }
      if (_dateIntegration != null) {
        fields['date_integration'] = _isoDate(_dateIntegration!);
      }
      final updated = await widget.api.updateVigileMultipart(
        vigileId: widget.vigileId,
        fields: fields,
        photoPath: _newPhotoPath,
        idDocumentPath: _newIdRectoPath,
        idDocumentVersoPath: _newIdVersoPath,
      );
      if (!mounted) return;
      setState(() {
        _data = updated;
        _newPhotoPath = null;
        _newIdRectoPath = null;
        _newIdVersoPath = null;
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
    final hasPhoto = _newPhotoPath != null || _data?['profile_photo'] != null;
    final ok = _data?['face_enrollment_ok'] == true;
    late final String label;
    late final Color bg;
    late final Color fg;
    if (!hasPhoto) {
      label = 'Sans photo';
      bg = const Color(0xFFF1F5F9);
      fg = const Color(0xFF64748B);
    } else if (ok) {
      label = 'Enregistré OK';
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

  Widget _placementBanner() {
    final placement = _data?['placement'];
    if (placement is! Map) return const SizedBox.shrink();
    if (placement['is_posted'] != true) return const SizedBox.shrink();

    final distinct = placement['distinct_sites'];
    final placements = placement['placements'];
    String headline = 'Posté actuellement';
    if (distinct is List && distinct.length == 1) {
      headline = 'Posté sur ${(distinct.first as Map)['site_name']}';
    } else if (distinct is List && distinct.length > 1) {
      headline = 'Posté sur ${distinct.length} sites';
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: GlassPanel(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.place_rounded, color: CobraAdminColors.indigo, size: 22),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    headline,
                    style: GoogleFonts.outfit(
                      fontWeight: FontWeight.w800,
                      fontSize: 15,
                      color: CobraAdminColors.ink,
                    ),
                  ),
                ),
              ],
            ),
            if (placements is List && placements.isNotEmpty) ...[
              const SizedBox(height: 10),
              ...placements.take(6).map((raw) {
                final p = raw as Map;
                return Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: Text(
                    '• ${p['site_name']} — ${p['role']} (${p['shift_label']})',
                    style: GoogleFonts.outfit(fontSize: 12, color: const Color(0xFF64748B)),
                  ),
                );
              }),
            ],
          ],
        ),
      ),
    );
  }

  Widget _idPreview({
    required String title,
    required String? networkUrl,
    required String? localPath,
    required VoidCallback onReplace,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(title, style: GoogleFonts.outfit(fontWeight: FontWeight.w700, fontSize: 13)),
        const SizedBox(height: 8),
        if (localPath != null)
          ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: Image.file(File(localPath), height: 120, fit: BoxFit.cover),
          )
        else if (networkUrl != null)
          ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: Image.network(networkUrl, height: 120, fit: BoxFit.cover),
          )
        else
          Container(
            height: 80,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: const Color(0xFFF8FAFC),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: const Color(0xFFE2E8F0)),
            ),
            child: Text(
              'Aucun fichier',
              style: GoogleFonts.outfit(color: const Color(0xFF94A3B8), fontSize: 12),
            ),
          ),
        const SizedBox(height: 6),
        OutlinedButton.icon(
          onPressed: onReplace,
          icon: const Icon(Icons.upload_file_outlined, size: 18),
          label: const Text('Remplacer'),
        ),
      ],
    );
  }

  Widget _metaRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          SizedBox(
            width: 120,
            child: Text(
              label,
              style: GoogleFonts.outfit(fontSize: 12, color: const Color(0xFF64748B)),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: GoogleFonts.outfit(fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final photoUrl = _newPhotoPath != null
        ? null
        : widget.api.resolveMediaUrl(_data?['profile_photo']?.toString());
    final idRectoUrl = widget.api.resolveMediaUrl(_data?['id_document']?.toString());
    final idVersoUrl = widget.api.resolveMediaUrl(_data?['id_document_verso']?.toString());

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
          ? const Center(child: CircularProgressIndicator(color: CobraAdminColors.indigo))
          : Form(
              key: _formKey,
              child: ListView(
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
                children: [
                  _placementBanner(),
                  GlassPanel(
                    child: Column(
                      children: [
                        Text(
                          'Portrait',
                          style: GoogleFonts.outfit(fontWeight: FontWeight.w800, fontSize: 15),
                        ),
                        const SizedBox(height: 12),
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
                  Text(
                    'Modifier la fiche',
                    style: GoogleFonts.outfit(fontWeight: FontWeight.w800, fontSize: 16),
                  ),
                  const SizedBox(height: 12),
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
                    decoration: _dec('Courriel'),
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
                    maxLines: 3,
                  ),
                  const SizedBox(height: 12),
                  TextFormField(controller: _aval, decoration: _dec('Aval')),
                  const SizedBox(height: 12),
                  OutlinedButton.icon(
                    onPressed: _pickIntegrationDate,
                    icon: const Icon(Icons.calendar_today_outlined, size: 18),
                    label: Text(
                      _dateIntegration != null
                          ? 'Intégration : ${_displayDate(_dateIntegration!)}'
                          : "Date d'intégration (optionnel)",
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _height,
                    decoration: _dec('Taille (cm)'),
                    keyboardType: TextInputType.number,
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
                                child: Text(o.label),
                              ),
                            )
                            .toList(),
                        onChanged: (v) => setState(() => _educationLevel = v ?? ''),
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Compte actif (connexion autorisée)'),
                    value: _isActive,
                    activeThumbColor: CobraAdminColors.indigo,
                    onChanged: (v) => setState(() => _isActive = v),
                  ),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Marqué en service'),
                    value: _onDuty,
                    activeThumbColor: CobraAdminColors.indigo,
                    onChanged: (v) => setState(() => _onDuty = v),
                  ),
                  const SizedBox(height: 16),
                  GlassPanel(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Text(
                          "Carte d'identité",
                          style: GoogleFonts.outfit(fontWeight: FontWeight.w800, fontSize: 15),
                        ),
                        const SizedBox(height: 12),
                        _idPreview(
                          title: 'Recto (face avant)',
                          networkUrl: idRectoUrl,
                          localPath: _newIdRectoPath,
                          onReplace: () => _pickId(verso: false),
                        ),
                        const SizedBox(height: 16),
                        _idPreview(
                          title: 'Verso (face arrière)',
                          networkUrl: idVersoUrl,
                          localPath: _newIdVersoPath,
                          onReplace: () => _pickId(verso: true),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),
                  GlassPanel(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Text(
                          'Résumé',
                          style: GoogleFonts.outfit(fontWeight: FontWeight.w800, fontSize: 15),
                        ),
                        const SizedBox(height: 10),
                        _metaRow('Rôle', 'Vigile'),
                        _metaRow(
                          'Niveau d\'études',
                          _educationLabel(_data?['education_level']?.toString()),
                        ),
                        if (_data?['height_cm'] != null)
                          _metaRow('Taille', '${_data!['height_cm']} cm'),
                        _metaRow('Inscription', _formatDateTime(_data?['date_joined'])),
                        _metaRow('Dernière connexion', _formatDateTime(_data?['last_login'])),
                      ],
                    ),
                  ),
                  const SizedBox(height: 24),
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
                            'Enregistrer les modifications',
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
