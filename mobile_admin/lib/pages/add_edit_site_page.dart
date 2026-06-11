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
  late final TextEditingController _managerName;
  late final TextEditingController _managerPhone;
  late final TextEditingController _siteSmsPhone;
  late final TextEditingController _lat;
  late final TextEditingController _lng;
  late final TextEditingController _radius;
  late final TextEditingController _gpsMargin;
  late final TextEditingController _lateTol;
  late final TextEditingController _reliefLate;
  late final TextEditingController _timezone;
  late final TextEditingController _dayStaff;
  late final TextEditingController _nightStaff;
  late DateTime _creationDate;
  late TimeOfDay _startTime;
  late TimeOfDay _endTime;
  bool _active = true;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    final m = widget.existing;
    _name = TextEditingController(text: m?['name']?.toString() ?? '');
    _address = TextEditingController(text: m?['address']?.toString() ?? '');
    _managerName = TextEditingController(
      text: m?['site_manager_name']?.toString() ?? '',
    );
    _managerPhone = TextEditingController(
      text: m?['site_manager_phone']?.toString() ?? '',
    );
    _siteSmsPhone = TextEditingController(
      text: m?['site_sms_phone']?.toString() ?? '',
    );
    _lat = TextEditingController(text: m?['latitude']?.toString() ?? '');
    _lng = TextEditingController(text: m?['longitude']?.toString() ?? '');
    _radius = TextEditingController(
      text: (m?['geofence_radius_meters'] ?? 250).toString(),
    );
    _gpsMargin = TextEditingController(
      text: (m?['geofence_gps_margin_meters'] ?? 75).toString(),
    );
    final lateMin = m?['late_tolerance_minutes'] ?? m?['relief_late_alert_minutes'] ?? 15;
    _lateTol = TextEditingController(text: lateMin.toString());
    _reliefLate = TextEditingController(text: lateMin.toString());
    _dayStaff = TextEditingController(
      text: (m?['day_staff_required'] ?? 1).toString(),
    );
    _nightStaff = TextEditingController(
      text: (m?['night_staff_required'] ?? 1).toString(),
    );
    final tz = m?['timezone'];
    _timezone = TextEditingController(
      text: tz != null && tz.toString().isNotEmpty
          ? tz.toString()
          : 'Africa/Abidjan',
    );
    _startTime = _parseTime(m?['expected_start_time'], const TimeOfDay(hour: 6, minute: 0));
    _endTime = _parseTime(m?['expected_end_time'], const TimeOfDay(hour: 18, minute: 0));
    _creationDate = _parseCreationDate(m?['created_at']) ?? DateTime.now();
    if (m != null) {
      _active = m['is_active'] == true || m['is_active'] == 1;
    }
  }

  @override
  void dispose() {
    _name.dispose();
    _address.dispose();
    _managerName.dispose();
    _managerPhone.dispose();
    _siteSmsPhone.dispose();
    _lat.dispose();
    _lng.dispose();
    _radius.dispose();
    _gpsMargin.dispose();
    _lateTol.dispose();
    _reliefLate.dispose();
    _timezone.dispose();
    _dayStaff.dispose();
    _nightStaff.dispose();
    super.dispose();
  }

  TimeOfDay _parseTime(dynamic raw, TimeOfDay fallback) {
    if (raw == null) return fallback;
    final parts = raw.toString().split(':');
    if (parts.length >= 2) {
      final h = int.tryParse(parts[0]);
      final m = int.tryParse(parts[1]);
      if (h != null && m != null) return TimeOfDay(hour: h, minute: m);
    }
    return fallback;
  }

  DateTime? _parseCreationDate(dynamic raw) {
    if (raw == null) return null;
    final s = raw.toString();
    if (s.length >= 10) {
      return DateTime.tryParse(s.substring(0, 10));
    }
    return null;
  }

  String _isoDate(DateTime d) =>
      '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  String _displayDate(DateTime d) =>
      '${d.day.toString().padLeft(2, '0')}/${d.month.toString().padLeft(2, '0')}/${d.year}';

  String _formatApiTime(TimeOfDay t) {
    final h = t.hour.toString().padLeft(2, '0');
    final m = t.minute.toString().padLeft(2, '0');
    return '$h:$m:00';
  }

  String _displayTime(TimeOfDay t) {
    final h = t.hour.toString().padLeft(2, '0');
    final m = t.minute.toString().padLeft(2, '0');
    return '$h:$m';
  }

  int? _parseInt(String s, int fallback) {
    final v = int.tryParse(s.trim());
    return v ?? fallback;
  }

  void _syncTolerancePair() {
    _reliefLate.text = _lateTol.text;
  }

  int _toleranceMinutes() => _parseInt(_lateTol.text, 15) ?? 15;

  Future<void> _pickCreationDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _creationDate,
      firstDate: DateTime(2000),
      lastDate: DateTime.now().add(const Duration(days: 365)),
    );
    if (picked != null && mounted) setState(() => _creationDate = picked);
  }

  Future<void> _pickTime({required bool start}) async {
    final picked = await showTimePicker(
      context: context,
      initialTime: start ? _startTime : _endTime,
    );
    if (picked != null && mounted) {
      setState(() {
        if (start) {
          _startTime = picked;
        } else {
          _endTime = picked;
        }
      });
    }
  }

  Map<String, dynamic> _buildPayload({required bool includeCreationDate}) {
    final latStr = _lat.text.trim().replaceAll(',', '.');
    final lngStr = _lng.text.trim().replaceAll(',', '.');
    double? lat;
    double? lng;
    if (latStr.isNotEmpty || lngStr.isNotEmpty) {
      lat = double.tryParse(latStr);
      lng = double.tryParse(lngStr);
    }

    final body = <String, dynamic>{
      'name': _name.text.trim(),
      'address': _address.text.trim(),
      'site_manager_name': _managerName.text.trim(),
      'site_manager_phone': _managerPhone.text.trim(),
      'site_sms_phone': _siteSmsPhone.text.trim(),
      'timezone': _timezone.text.trim().isEmpty
          ? 'Africa/Abidjan'
          : _timezone.text.trim(),
      'expected_start_time': _formatApiTime(_startTime),
      'expected_end_time': _formatApiTime(_endTime),
      'day_staff_required': _parseInt(_dayStaff.text, 1),
      'night_staff_required': _parseInt(_nightStaff.text, 1),
      'geofence_radius_meters': _parseInt(_radius.text, 250),
      'geofence_gps_margin_meters': _parseInt(_gpsMargin.text, 75),
      'late_tolerance_minutes': _toleranceMinutes(),
      'relief_late_alert_minutes': _toleranceMinutes(),
      'is_active': _active,
    };
    if (includeCreationDate) {
      body['creation_date'] = _isoDate(_creationDate);
    }
    if (lat != null && lng != null) {
      body['latitude'] = lat.toString();
      body['longitude'] = lng.toString();
    } else if (widget.isEdit) {
      body['latitude'] = null;
      body['longitude'] = null;
    }
    return body;
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final latStr = _lat.text.trim().replaceAll(',', '.');
    final lngStr = _lng.text.trim().replaceAll(',', '.');
    if (latStr.isNotEmpty || lngStr.isNotEmpty) {
      if (latStr.isEmpty || lngStr.isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Renseignez la latitude et la longitude ensemble, ou laissez les deux vides.',
            ),
          ),
        );
        return;
      }
      if (double.tryParse(latStr) == null || double.tryParse(lngStr) == null) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Latitude / longitude invalides.')),
        );
        return;
      }
    }

    setState(() => _saving = true);
    try {
      if (widget.isEdit) {
        final id = (widget.existing!['id'] as num).toInt();
        await widget.api.updateSite(
          id,
          _buildPayload(includeCreationDate: true),
        );
      } else {
        await widget.api.createSite(
          _buildPayload(includeCreationDate: true),
        );
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

  Widget _timeButton(String label, TimeOfDay time, VoidCallback onTap) {
    return OutlinedButton(
      onPressed: onTap,
      style: OutlinedButton.styleFrom(
        padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 16),
      ),
      child: Row(
        children: [
          Expanded(
            child: Text(
              label,
              style: GoogleFonts.outfit(
                fontSize: 13,
                color: const Color(0xFF64748B),
              ),
            ),
          ),
          Text(
            _displayTime(time),
            style: GoogleFonts.outfit(
              fontWeight: FontWeight.w800,
              fontSize: 16,
              color: CobraAdminColors.ink,
            ),
          ),
        ],
      ),
    );
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
            Text(
              'Mêmes champs que le tableau de bord web.',
              style: GoogleFonts.outfit(fontSize: 13, color: const Color(0xFF64748B)),
            ),
            const SizedBox(height: 16),
            Text(
              'Date de création du site',
              style: GoogleFonts.outfit(
                fontWeight: FontWeight.w700,
                fontSize: 13,
                color: const Color(0xFF64748B),
              ),
            ),
            const SizedBox(height: 6),
            OutlinedButton.icon(
              onPressed: _pickCreationDate,
              icon: const Icon(Icons.calendar_today_outlined, size: 18),
              label: Text(
                _displayDate(_creationDate),
                style: GoogleFonts.outfit(fontWeight: FontWeight.w700),
              ),
              style: OutlinedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 16),
              ),
            ),
            const SizedBox(height: 16),
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
            TextFormField(
              controller: _managerName,
              decoration: _dec('Nom du responsable du site', hint: 'Ex. Kouassi Jean'),
              style: GoogleFonts.outfit(),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _managerPhone,
              decoration: _dec('Téléphone du responsable du site *'),
              keyboardType: TextInputType.phone,
              validator: (v) {
                final t = v?.trim() ?? '';
                if (t.isEmpty) return 'Obligatoire';
                if (t.length < 8) return 'Numéro trop court';
                return null;
              },
              style: GoogleFonts.outfit(),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _siteSmsPhone,
              decoration: _dec('Numéro SMS du site (optionnel)'),
              keyboardType: TextInputType.phone,
              validator: (v) {
                final t = v?.trim() ?? '';
                if (t.isNotEmpty && t.length < 8) return 'Numéro trop court';
                return null;
              },
              style: GoogleFonts.outfit(),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _timezone,
              decoration: _dec('Fuseau horaire', hint: 'Africa/Abidjan'),
              style: GoogleFonts.outfit(),
            ),
            const SizedBox(height: 12),
            _timeButton(
              'Heure de prise de service attendue',
              _startTime,
              () => _pickTime(start: true),
            ),
            const SizedBox(height: 8),
            _timeButton(
              'Heure de fin de service attendue',
              _endTime,
              () => _pickTime(start: false),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: TextFormField(
                    controller: _dayStaff,
                    decoration: _dec('Effectif poste jour', hint: '06h–18h'),
                    keyboardType: TextInputType.number,
                    validator: (v) {
                      final n = int.tryParse(v?.trim() ?? '');
                      if (n == null || n < 1) return 'Min. 1';
                      return null;
                    },
                    style: GoogleFonts.outfit(),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: TextFormField(
                    controller: _nightStaff,
                    decoration: _dec('Effectif poste nuit', hint: '18h–06h'),
                    keyboardType: TextInputType.number,
                    validator: (v) {
                      final n = int.tryParse(v?.trim() ?? '');
                      if (n == null || n < 1) return 'Min. 1';
                      return null;
                    },
                    style: GoogleFonts.outfit(),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _lateTol,
              decoration: _dec('Tolérance de retard (prise de service, min)'),
              keyboardType: TextInputType.number,
              onChanged: (_) => _syncTolerancePair(),
              style: GoogleFonts.outfit(),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _reliefLate,
              readOnly: true,
              decoration: _dec('Alerte relève non arrivée (min) — synchronisé'),
              style: GoogleFonts.outfit(color: const Color(0xFF64748B)),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: TextFormField(
                    controller: _lat,
                    decoration: _dec('Latitude (optionnel)'),
                    keyboardType: const TextInputType.numberWithOptions(
                      decimal: true,
                      signed: true,
                    ),
                    style: GoogleFonts.outfit(),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: TextFormField(
                    controller: _lng,
                    decoration: _dec('Longitude (optionnel)'),
                    keyboardType: const TextInputType.numberWithOptions(
                      decimal: true,
                      signed: true,
                    ),
                    style: GoogleFonts.outfit(),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _radius,
              decoration: _dec('Rayon géofence (mètres)'),
              keyboardType: TextInputType.number,
              style: GoogleFonts.outfit(),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _gpsMargin,
              decoration: _dec('Marge GPS géofence (mètres)'),
              keyboardType: TextInputType.number,
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

  InputDecoration _dec(String label, {String? hint}) {
    return InputDecoration(
      labelText: label,
      hintText: hint,
      labelStyle: GoogleFonts.outfit(color: const Color(0xFF64748B)),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
    );
  }
}
