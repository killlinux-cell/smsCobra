import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../services/admin_api.dart';
import '../theme/cobra_admin_theme.dart';

class AddEditSitePage extends StatefulWidget {
  const AddEditSitePage({
    super.key,
    required this.api,
    required this.onSessionExpired,
    this.existing,
  });

  final AdminApi api;
  final Future<void> Function() onSessionExpired;
  final Map<String, dynamic>? existing;

  bool get isEdit => existing != null;

  @override
  State<AddEditSitePage> createState() => _AddEditSitePageState();
}

class _AddEditSitePageState extends State<AddEditSitePage> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _name;
  late final TextEditingController _address;
  late final TextEditingController _lat;
  late final TextEditingController _lng;
  late final TextEditingController _radius;
  late final TextEditingController _gpsMargin;
  late final TextEditingController _lateTol;
  late final TextEditingController _timezone;
  bool _active = true;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    final m = widget.existing;
    _name = TextEditingController(text: m?['name']?.toString() ?? '');
    _address = TextEditingController(text: m?['address']?.toString() ?? '');
    _lat = TextEditingController(text: m?['latitude']?.toString() ?? '');
    _lng = TextEditingController(text: m?['longitude']?.toString() ?? '');
    _radius = TextEditingController(
      text: (m?['geofence_radius_meters'] ?? 250).toString(),
    );
    _gpsMargin = TextEditingController(
      text: (m?['geofence_gps_margin_meters'] ?? 75).toString(),
    );
    _lateTol = TextEditingController(
      text: (m?['late_tolerance_minutes'] ?? 15).toString(),
    );
    final tz = m?['timezone'];
    _timezone = TextEditingController(
      text: tz != null && tz.toString().isNotEmpty
          ? tz.toString()
          : 'Africa/Abidjan',
    );
    if (m != null) {
      _active = m['is_active'] == true || m['is_active'] == 1;
    }
  }

  @override
  void dispose() {
    _name.dispose();
    _address.dispose();
    _lat.dispose();
    _lng.dispose();
    _radius.dispose();
    _gpsMargin.dispose();
    _lateTol.dispose();
    _timezone.dispose();
    super.dispose();
  }

  int? _parseInt(String s, int fallback) {
    final v = int.tryParse(s.trim());
    return v ?? fallback;
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final lat = double.tryParse(_lat.text.trim().replaceAll(',', '.'));
    final lng = double.tryParse(_lng.text.trim().replaceAll(',', '.'));
    if (lat == null || lng == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Latitude / longitude invalides.')),
      );
      return;
    }

    setState(() => _saving = true);
    try {
      if (widget.isEdit) {
        final id = (widget.existing!['id'] as num).toInt();
        await widget.api.updateSite(id, {
          'name': _name.text.trim(),
          'address': _address.text.trim(),
          'latitude': lat.toString(),
          'longitude': lng.toString(),
          'geofence_radius_meters': _parseInt(_radius.text, 250),
          'geofence_gps_margin_meters': _parseInt(_gpsMargin.text, 75),
          'late_tolerance_minutes': _parseInt(_lateTol.text, 15),
          'timezone': _timezone.text.trim().isEmpty
              ? 'Africa/Abidjan'
              : _timezone.text.trim(),
          'is_active': _active,
        });
      } else {
        await widget.api.createSite({
          'name': _name.text.trim(),
          'address': _address.text.trim(),
          'latitude': lat.toString(),
          'longitude': lng.toString(),
          'timezone': _timezone.text.trim().isEmpty
              ? 'Africa/Abidjan'
              : _timezone.text.trim(),
          'expected_start_time': '06:00:00',
          'expected_end_time': '18:00:00',
          'late_tolerance_minutes': _parseInt(_lateTol.text, 15),
          'geofence_radius_meters': _parseInt(_radius.text, 250),
          'geofence_gps_margin_meters': _parseInt(_gpsMargin.text, 75),
          'is_active': _active,
        });
      }
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
    final title = widget.isEdit ? 'Modifier le site' : 'Nouveau site';
    return Scaffold(
      backgroundColor: CobraAdminColors.surface,
      appBar: AppBar(
        title: Text(title, style: GoogleFonts.outfit(fontWeight: FontWeight.w800)),
        backgroundColor: CobraAdminColors.surface,
        foregroundColor: CobraAdminColors.ink,
        elevation: 0,
      ),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
          children: [
            TextFormField(
              controller: _name,
              decoration: _dec('Nom du site *'),
              validator: (v) =>
                  (v == null || v.trim().isEmpty) ? 'Obligatoire' : null,
              style: GoogleFonts.outfit(),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _address,
              decoration: _dec('Adresse *'),
              maxLines: 2,
              validator: (v) =>
                  (v == null || v.trim().isEmpty) ? 'Obligatoire' : null,
              style: GoogleFonts.outfit(),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: TextFormField(
                    controller: _lat,
                    decoration: _dec('Latitude *'),
                    keyboardType: const TextInputType.numberWithOptions(
                      decimal: true,
                      signed: true,
                    ),
                    validator: (v) =>
                        (v == null || v.trim().isEmpty) ? 'Obligatoire' : null,
                    style: GoogleFonts.outfit(),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: TextFormField(
                    controller: _lng,
                    decoration: _dec('Longitude *'),
                    keyboardType: const TextInputType.numberWithOptions(
                      decimal: true,
                      signed: true,
                    ),
                    validator: (v) =>
                        (v == null || v.trim().isEmpty) ? 'Obligatoire' : null,
                    style: GoogleFonts.outfit(),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _radius,
              decoration: _dec('Rayon géofence (m)'),
              keyboardType: TextInputType.number,
              style: GoogleFonts.outfit(),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _gpsMargin,
              decoration: _dec('Marge GPS (m)'),
              keyboardType: TextInputType.number,
              style: GoogleFonts.outfit(),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _lateTol,
              decoration: _dec('Tolérance retard (min)'),
              keyboardType: TextInputType.number,
              style: GoogleFonts.outfit(),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _timezone,
              decoration: _dec('Fuseau (ex. Africa/Abidjan)'),
              style: GoogleFonts.outfit(),
            ),
            const SizedBox(height: 8),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: Text('Site actif', style: GoogleFonts.outfit()),
              value: _active,
              activeThumbColor: CobraAdminColors.indigo,
              onChanged: (v) => setState(() => _active = v),
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
                      widget.isEdit ? 'Enregistrer' : 'Créer le site',
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
