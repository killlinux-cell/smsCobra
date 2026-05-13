import 'dart:async';

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:geolocator/geolocator.dart';

import '../models/agent_profile.dart';
import '../models/assignment.dart';
import '../services/cobra_api.dart';
import '../utils/assignment_pick.dart';
import '../utils/time_utils.dart';
import '../widgets/agent_home_header.dart';
import '../widgets/glass_card.dart';
import '../widgets/modern_action_button.dart';
import 'face_capture_page.dart';
import 'login_page.dart';

class AgentHomePage extends StatefulWidget {
  const AgentHomePage({super.key, required this.api});
  final CobraApi api;

  @override
  State<AgentHomePage> createState() => _AgentHomePageState();
}

class _AgentHomePageState extends State<AgentHomePage>
    with SingleTickerProviderStateMixin {
  bool loading = true;
  bool profileLoading = true;
  bool profileLoadFailed = false;
  AgentProfile? profile;
  List<Assignment> assignments = [];
  Assignment? selected;
  String feedback = "Synchronisé.";
  bool serviceStarted = false;
  DateTime? nextPresenceDue;
  Timer? presenceCountdownTimer;

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
    _load();
  }

  @override
  void dispose() {
    _pulseCtrl.dispose();
    presenceCountdownTimer?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      loading = true;
      if (profile == null) profileLoading = true;
      profileLoadFailed = false;
    });
    try {
      final result = await widget.api.fetchTodayAssignments();
      AgentProfile? me;
      try {
        me = await widget.api.fetchMe();
      } catch (_) {
        profileLoadFailed = true;
      }
      if (!mounted) return;
      final active = pickActiveAssignment(result, DateTime.now());
      setState(() {
        assignments = result;
        selected = active;
        profile = me ?? profile;
        profileLoading = false;
        feedback = "Planning synchronisé.";
        serviceStarted = selected != null && selected!.hasStart && !selected!.hasEnd;
        nextPresenceDue = parseIsoOrNull(selected?.presenceDueAtIso);
        if (serviceStarted) {
          _startPresenceCountdown();
        } else {
          _stopPresenceCountdown();
        }
      });
    } catch (_) {
      if (mounted) {
        setState(() {
          feedback = "Erreur de synchronisation.";
          profileLoading = false;
        });
      }
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<({String lat, String lon})> _getCurrentLatLon() async {
    final serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      throw Exception("gps_disabled");
    }

    LocationPermission permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.denied ||
        permission == LocationPermission.deniedForever) {
      throw Exception("gps_denied");
    }

    Future<Position> readFix() => Geolocator.getCurrentPosition(
          locationSettings: const LocationSettings(
            accuracy: LocationAccuracy.best,
            distanceFilter: 0,
            timeLimit: Duration(seconds: 28),
          ),
        );

    var pos = await readFix().timeout(const Duration(seconds: 30));
    // Une ancienne position en cache peut placer le vigile à des centaines de mètres du site réel.
    for (var attempt = 0; attempt < 2; attempt++) {
      final age = DateTime.now().difference(pos.timestamp);
      if (age <= const Duration(seconds: 90)) break;
      await Future<void>.delayed(const Duration(milliseconds: 500));
      pos = await readFix().timeout(const Duration(seconds: 30));
    }

    // (0,0) ou quasi = GPS non prêt / mock / erreur → le serveur affiche des milliers de km « hors zone ».
    if (pos.latitude.abs() < 0.0002 && pos.longitude.abs() < 0.0002) {
      throw Exception("gps_invalid_zero");
    }
    if (pos.isMocked) {
      throw Exception("gps_mocked");
    }
    if (DateTime.now().difference(pos.timestamp) > const Duration(minutes: 3)) {
      throw Exception("gps_stale");
    }

    return (
      lat: pos.latitude.toStringAsFixed(6),
      lon: pos.longitude.toStringAsFixed(6),
    );
  }

  void _startPresenceCountdown() {
    presenceCountdownTimer?.cancel();
    presenceCountdownTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      if (!mounted) return;
      setState(() {});
    });
  }

  void _stopPresenceCountdown() {
    presenceCountdownTimer?.cancel();
    presenceCountdownTimer = null;
  }

  bool get _presenceDueNow {
    if (!serviceStarted) return false;
    if (nextPresenceDue == null) return false;
    final now = DateTime.now();
    return now.isAfter(nextPresenceDue!) || now.isAtSameMomentAs(nextPresenceDue!);
  }

  double get _presenceProgress {
    if (!serviceStarted || nextPresenceDue == null) return 0;
    final remaining = nextPresenceDue!.difference(DateTime.now()).inSeconds;
    final clamped = remaining.clamp(0, 3600);
    return 1 - (clamped / 3600);
  }

  String _remainingPresenceText() {
    if (!serviceStarted || nextPresenceDue == null) return "";
    final d = nextPresenceDue!.difference(DateTime.now());
    if (d.isNegative) return "00:00";
    final minutes = d.inMinutes;
    final seconds = d.inSeconds % 60;
    return "${minutes.toString().padLeft(2, '0')}:${seconds.toString().padLeft(2, '0')}";
  }

  Future<void> _checkin(String type) async {
    if (selected == null) {
      setState(() => feedback = "Aucune affectation disponible.");
      return;
    }
    final imgPath = await FaceCapturePage.capture(
      context,
      title: "Reconnaissance faciale",
      hint: "Centrez votre visage dans le cadran pour valider le pointage.",
    );
    if (imgPath == null) {
      setState(() => feedback = "Selfie obligatoire: pointage annulé.");
      return;
    }
    try {
      final challengeId = await widget.api.requestBiometricChallenge(
        assignmentId: selected!.id,
        checkinType: type,
        deviceId: "mobile_agent",
      );
      final verificationToken = await widget.api.verifyBiometric(
        challengeId: challengeId,
        selfiePath: imgPath,
      );
      final gps = await _getCurrentLatLon();
      final resp = await widget.api.sendCheckin(
        type: type,
        assignmentId: selected!.id,
        photoPath: imgPath,
        latitude: gps.lat,
        longitude: gps.lon,
        verificationToken: verificationToken,
      );
      setState(() => feedback = resp);
      await _load();
    } catch (e) {
      final msg = _checkinErrorMessage(e);
      setState(() => feedback = msg);
    }
  }

  String _checkinErrorMessage(Object e) {
    final s = e.toString();
    if (s.contains("gps_invalid_zero")) {
      return "GPS invalide (position nulle). Activez la localisation, mode haute précision, attendez le fix satellite puis réessayez.";
    }
    if (s.contains("gps_mocked")) {
      return "Position simulée détectée. Désactivez les fausses positions (paramètres développeur) pour pointer.";
    }
    if (s.contains("gps_disabled")) {
      return "Activez le GPS / la localisation dans les paramètres du téléphone.";
    }
    if (s.contains("gps_denied")) {
      return "Autorisez l’app à accéder à la position (paramètres → Applications).";
    }
    if (s.contains("gps_stale")) {
      return "Position GPS trop ancienne. Attendez le fix (icône précise), déplacez-vous légèrement à l’air libre puis réessayez.";
    }
    if (s.contains("biometric_challenge_failed")) {
      return "Impossible de démarrer la vérification faciale. Vérifiez votre connexion puis réessayez.";
    }
    if (s.contains("biometric_verify_failed")) {
      return "Vérification faciale refusée. Reprenez un selfie bien cadré puis réessayez.";
    }
    return "Pointage refusé. Vérifiez la connexion, le GPS et que vous êtes au bon poste.";
  }

  Future<void> _logout() async {
    await widget.api.logout();
    if (!mounted) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => LoginPage(api: widget.api)),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF1F5FF),
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          AgentBrandHeader(
            onSync: _load,
            onLogout: _logout,
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 0),
            child: Transform.translate(
              offset: const Offset(0, -16),
              child: VigileOnlineCard(
                profile: profile,
                pulse: _pulse,
                photoUrl: widget.api.resolveMediaUrl(profile?.profilePhotoPath),
                loading: profileLoading,
                profileLoadFailed: profileLoadFailed,
              ),
            ),
          ),
          Expanded(
            child: loading
                ? const Center(child: CircularProgressIndicator())
                : Stack(
                    children: [
                      Container(
                        decoration: const BoxDecoration(
                          gradient: LinearGradient(
                            begin: Alignment.topCenter,
                            end: Alignment.bottomCenter,
                            colors: [
                              Color(0xFFEDEFFF),
                              Color(0xFFF9FAFF),
                              Color(0xFFF2F8FF),
                            ],
                          ),
                        ),
                      ),
                      Positioned(
                        top: -40,
                        right: -30,
                        child: Container(
                          width: 180,
                          height: 180,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: const Color(0xFF6366F1).withAlpha(28),
                          ),
                        ),
                      ),
                      SingleChildScrollView(
                        padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            GlassCard(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    children: [
                                      Icon(
                                        Icons.calendar_today_rounded,
                                        size: 20,
                                        color: Colors.indigo.shade700,
                                      ),
                                      const SizedBox(width: 8),
                                      Text(
                                        selected == null
                                            ? "Aucun poste sélectionné"
                                            : "Poste du ${_formatShiftDate(selected!.shiftDate)}",
                                        style: TextStyle(
                                          fontWeight: FontWeight.w800,
                                          fontSize: 16,
                                          color: Colors.indigo.shade900,
                                        ),
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 12),
                                  _PosteMissionHighlight(assignment: selected),
                                  const SizedBox(height: 16),
                                  const Divider(height: 1),
                              const SizedBox(height: 14),
                              Text(
                                "Pointage début / fin",
                                style: TextStyle(
                                  fontWeight: FontWeight.w700,
                                  fontSize: 13,
                                  color: Colors.grey.shade700,
                                ),
                              ),
                              const SizedBox(height: 10),
                              Row(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Expanded(
                                    child: _ShiftActionTile(
                                      title: "Prise de service",
                                      subtitle: selected?.hasStart == true
                                          ? "Effectuée"
                                          : "Selfie + GPS",
                                      icon: Icons.login_rounded,
                                      accent: const Color(0xFF4F46E5),
                                      filled: selected?.hasStart == true,
                                      enabled: selected != null &&
                                          selected!.hasStart != true,
                                      onTap: () => _checkin("start"),
                                    ),
                                  ),
                                  const SizedBox(width: 10),
                                  Expanded(
                                    child: _ShiftActionTile(
                                      title: "Fin de service",
                                      subtitle: selected?.hasEnd == true
                                          ? "Effectuée"
                                          : (selected?.canEnd == true
                                              ? "Selfie + GPS"
                                              : "Non disponible"),
                                      icon: Icons.logout_rounded,
                                      accent: const Color(0xFF0284C7),
                                      filled: selected?.hasEnd == true,
                                      enabled: selected != null &&
                                          selected!.canEnd == true,
                                      onTap: () => _checkin("end"),
                                    ),
                                  ),
                                ],
                              ),
                              if (selected != null &&
                                  !selected!.canEnd &&
                                  selected!.endBlockReason != null) ...[
                                const SizedBox(height: 10),
                                Container(
                                  width: double.infinity,
                                  padding: const EdgeInsets.all(10),
                                  decoration: BoxDecoration(
                                    color: const Color(0xFFF1F5F9),
                                    borderRadius: BorderRadius.circular(10),
                                  ),
                                  child: Text(
                                    selected!.endBlockReason!,
                                    style: const TextStyle(
                                      color: Color(0xFF475569),
                                      fontSize: 12,
                                      height: 1.35,
                                    ),
                                  ),
                                ),
                              ],
                              const SizedBox(height: 10),
                              Text(
                                "Les pointages sont liés à l’affectation affichée (date du poste prise en compte).",
                                style: TextStyle(
                                  color: Colors.grey.shade600,
                                  fontSize: 11,
                                ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 14),
                        GlassCard(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Row(
                                children: [
                                  Icon(
                                    Icons.timelapse_rounded,
                                    color: Color(0xFF0F766E),
                                  ),
                                  SizedBox(width: 8),
                                  Text(
                                    "Présence horaire (selfie + GPS)",
                                    style: TextStyle(fontWeight: FontWeight.w800),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 8),
                              Text(
                                serviceStarted
                                    ? "Prochaine confirmation dans: ${_remainingPresenceText()}"
                                    : "Commencez par la prise de service.",
                                style: const TextStyle(color: Color(0xFF6B7280)),
                              ),
                              const SizedBox(height: 12),
                              Row(
                                children: [
                                  SizedBox(
                                    width: 42,
                                    height: 42,
                                    child: TweenAnimationBuilder<double>(
                                      tween: Tween<double>(
                                        begin: 0,
                                        end: _presenceProgress,
                                      ),
                                      duration: const Duration(milliseconds: 400),
                                      builder: (context, value, _) {
                                        return CircularProgressIndicator(
                                          value: value,
                                          strokeWidth: 4,
                                          backgroundColor: const Color(0xFFE2E8F0),
                                        );
                                      },
                                    ),
                                  ),
                                  const SizedBox(width: 10),
                                  Expanded(
                                    child: Text(
                                      _presenceDueNow
                                          ? "Présence attendue maintenant."
                                          : "Progression vers la prochaine présence.",
                                      style: const TextStyle(
                                        color: Color(0xFF64748B),
                                        fontSize: 12,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 10),
                              ModernActionButton(
                                label: "Confirmer présence",
                                icon: Icons.timer_rounded,
                                enabled: serviceStarted && _presenceDueNow,
                                onTap: () => _checkin("presence"),
                                colors: const [
                                  Color(0xFF0F766E),
                                  Color(0xFF0E9F6E),
                                ],
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 14),
                        GlassCard(
                          child: Row(
                            children: [
                              const Icon(
                                Icons.info_outline_rounded,
                                color: Color(0xFF475569),
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  feedback,
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

String _formatShiftDate(DateTime d) {
  final dd = d.day.toString().padLeft(2, "0");
  final mm = d.month.toString().padLeft(2, "0");
  return "$dd/$mm/${d.year}";
}

/// Mise en avant du site et des horaires du poste actuel.
class _PosteMissionHighlight extends StatelessWidget {
  const _PosteMissionHighlight({required this.assignment});

  final Assignment? assignment;

  @override
  Widget build(BuildContext context) {
    if (assignment == null) {
      return Container(
        width: double.infinity,
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: const Color(0xFFF1F5F9),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: const Color(0xFFE2E8F0)),
        ),
        child: Row(
          children: [
            Icon(Icons.info_outline_rounded, color: Colors.grey.shade600),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                "Aucun poste actif pour le moment. Vérifiez votre planning ou actualisez.",
                style: GoogleFonts.outfit(
                  fontSize: 13,
                  color: const Color(0xFF64748B),
                  height: 1.35,
                ),
              ),
            ),
          ],
        ),
      );
    }

    final a = assignment!;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(18, 18, 18, 16),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            Color(0xFF3730A3),
            Color(0xFF4F46E5),
            Color(0xFF6366F1),
          ],
        ),
        borderRadius: BorderRadius.circular(18),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFF4F46E5).withAlpha(85),
            blurRadius: 20,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.white.withAlpha(40),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(
                  Icons.apartment_rounded,
                  color: Colors.white.withAlpha(240),
                  size: 22,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  "SITE D’AFFECTION",
                  style: GoogleFonts.outfit(
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 1.5,
                    color: Colors.white.withAlpha(210),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            a.siteName,
            style: GoogleFonts.outfit(
              fontSize: 24,
              fontWeight: FontWeight.w800,
              height: 1.15,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 20),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.white.withAlpha(36),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(
                  Icons.schedule_rounded,
                  color: Colors.white.withAlpha(240),
                  size: 22,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      "HORAIRES DE SERVICE",
                      style: GoogleFonts.outfit(
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 1.3,
                        color: Colors.white.withAlpha(210),
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      "${a.startTime} – ${a.endTime}",
                      style: GoogleFonts.outfit(
                        fontSize: 30,
                        fontWeight: FontWeight.w800,
                        height: 1.05,
                        color: Colors.white,
                        fontFeatures: const [FontFeature.tabularFigures()],
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      _creneauDescription(a.startTime, a.endTime),
                      style: GoogleFonts.outfit(
                        fontSize: 12,
                        fontWeight: FontWeight.w500,
                        color: Colors.white.withAlpha(200),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: BoxDecoration(
              color: Colors.black.withAlpha(35),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Text(
              "Poste synchronisé • affectation n°${a.id}",
              style: GoogleFonts.outfit(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: Colors.white.withAlpha(220),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

String _creneauDescription(String start, String end) {
  final sm = minutesFromHhMm(start);
  final em = minutesFromHhMm(end);
  if (sm > em) {
    return "Poste de nuit (passage minuit) — fin le lendemain matin.";
  }
  return "Créneau sur la journée planifiée.";
}

class _ShiftActionTile extends StatelessWidget {
  const _ShiftActionTile({
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.accent,
    required this.filled,
    required this.enabled,
    required this.onTap,
  });

  final String title;
  final String subtitle;
  final IconData icon;
  final Color accent;
  final bool filled;
  final bool enabled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final borderColor = filled
        ? const Color(0xFF22C55E)
        : (enabled ? accent : const Color(0xFFE2E8F0));
    final bg = filled
        ? const Color(0xFFF0FDF4)
        : (enabled ? accent.withAlpha(22) : const Color(0xFFF8FAFC));

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: enabled ? onTap : null,
        borderRadius: BorderRadius.circular(14),
        child: Ink(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
          decoration: BoxDecoration(
            color: bg,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: borderColor, width: enabled || filled ? 2 : 1),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(
                    icon,
                    size: 22,
                    color: filled
                        ? const Color(0xFF15803D)
                        : (enabled ? accent : const Color(0xFF94A3B8)),
                  ),
                  if (filled) ...[
                    const SizedBox(width: 6),
                    const Icon(
                      Icons.check_circle_rounded,
                      size: 18,
                      color: Color(0xFF16A34A),
                    ),
                  ],
                ],
              ),
              const SizedBox(height: 8),
              Text(
                title,
                style: TextStyle(
                  fontWeight: FontWeight.w800,
                  fontSize: 13,
                  color: enabled || filled
                      ? const Color(0xFF0F172A)
                      : const Color(0xFF94A3B8),
                ),
              ),
              const SizedBox(height: 2),
              Text(
                subtitle,
                style: TextStyle(
                  fontSize: 11,
                  color: Colors.grey.shade600,
                  height: 1.2,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
