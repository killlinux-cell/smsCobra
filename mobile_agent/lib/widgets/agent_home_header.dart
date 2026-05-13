import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../models/agent_profile.dart';

/// Bandeau marque + actions (sync / déconnexion).
class AgentBrandHeader extends StatelessWidget {
  const AgentBrandHeader({
    super.key,
    required this.onSync,
    required this.onLogout,
  });

  final VoidCallback onSync;
  final VoidCallback onLogout;

  @override
  Widget build(BuildContext context) {
    final topPad = MediaQuery.paddingOf(context).top;
    return Container(
      width: double.infinity,
      padding: EdgeInsets.fromLTRB(20, topPad + 8, 12, 20),
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            Color(0xFF1a0a0a),
            Color(0xFF7f1d1d),
            Color(0xFFb91c1c),
          ],
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: Colors.white.withAlpha(36),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: const Icon(
                            Icons.shield_moon_rounded,
                            color: Color(0xFFC0C0C0),
                            size: 26,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                "SMS",
                                style: GoogleFonts.outfit(
                                  fontSize: 26,
                                  fontWeight: FontWeight.w800,
                                  letterSpacing: 3,
                                  color: Colors.white,
                                  height: 1,
                                ),
                              ),
                              const SizedBox(height: 2),
                              Text(
                                "Agent",
                                style: GoogleFonts.outfit(
                                  fontSize: 15,
                                  fontWeight: FontWeight.w500,
                                  color: Colors.white.withAlpha(220),
                                  letterSpacing: 0.5,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 10),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 10,
                        vertical: 5,
                      ),
                      decoration: BoxDecoration(
                        color: Colors.black.withAlpha(35),
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(
                          color: Colors.white.withAlpha(50),
                        ),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            Icons.badge_outlined,
                            size: 16,
                            color: Colors.amber.shade100,
                          ),
                          const SizedBox(width: 6),
                          Text(
                            "Espace Agent",
                            style: GoogleFonts.outfit(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              color: Colors.white,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              Column(
                children: [
                  _RoundIconBtn(
                    icon: Icons.sync_rounded,
                    tooltip: "Actualiser",
                    onPressed: onSync,
                  ),
                  const SizedBox(height: 6),
                  _RoundIconBtn(
                    icon: Icons.logout_rounded,
                    tooltip: "Déconnexion",
                    onPressed: onLogout,
                  ),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _RoundIconBtn extends StatelessWidget {
  const _RoundIconBtn({
    required this.icon,
    required this.tooltip,
    required this.onPressed,
  });

  final IconData icon;
  final String tooltip;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white.withAlpha(45),
      shape: const CircleBorder(),
      clipBehavior: Clip.antiAlias,
      child: IconButton(
        tooltip: tooltip,
        onPressed: onPressed,
        icon: Icon(icon, color: Colors.white, size: 22),
      ),
    );
  }
}

/// Carte vigile connecté + indicateur « en ligne » animé.
class VigileOnlineCard extends StatelessWidget {
  const VigileOnlineCard({
    super.key,
    required this.profile,
    required this.pulse,
    required this.photoUrl,
    this.loading = false,
    this.profileLoadFailed = false,
  });

  final AgentProfile? profile;
  final Animation<double> pulse;
  final String? photoUrl;
  final bool loading;
  final bool profileLoadFailed;

  @override
  Widget build(BuildContext context) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: const Duration(milliseconds: 520),
      curve: Curves.easeOutCubic,
      builder: (context, t, child) {
        return Opacity(
          opacity: t,
          child: Transform.translate(
            offset: Offset(0, 16 * (1 - t)),
            child: child,
          ),
        );
      },
      child: Material(
        elevation: 8,
        shadowColor: const Color(0xFF4F46E5).withAlpha(80),
        borderRadius: BorderRadius.circular(20),
        color: Colors.white,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          child: loading
              ? _skeleton()
              : profile == null
                  ? _profileFallback(profileLoadFailed)
                  : Row(
                  children: [
                    _AvatarPulse(
                      pulse: pulse,
                      profile: profile!,
                      photoUrl: photoUrl,
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Flexible(
                                child: Text(
                                  profile!.displayName,
                                  style: GoogleFonts.outfit(
                                    fontSize: 17,
                                    fontWeight: FontWeight.w700,
                                    color: const Color(0xFF0F172A),
                                  ),
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 4),
                          Row(
                            children: [
                              Icon(
                                Icons.fingerprint_rounded,
                                size: 16,
                                color: Colors.indigo.shade400,
                              ),
                              const SizedBox(width: 4),
                              Text(
                                "Matricule ${profile!.matricule}",
                                style: GoogleFonts.outfit(
                                  fontSize: 13,
                                  fontWeight: FontWeight.w600,
                                  color: const Color(0xFF64748B),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 10),
                          AnimatedBuilder(
                            animation: pulse,
                            builder: (context, _) {
                              return Row(
                                children: [
                                  Transform.scale(
                                    scale: pulse.value,
                                    child: Container(
                                      width: 10,
                                      height: 10,
                                      decoration: BoxDecoration(
                                        shape: BoxShape.circle,
                                        color: const Color(0xFF22C55E),
                                        boxShadow: [
                                          BoxShadow(
                                            color: const Color(0xFF22C55E)
                                                .withAlpha((120 * pulse.value).round()),
                                            blurRadius: 8 * pulse.value,
                                            spreadRadius: 1,
                                          ),
                                        ],
                                      ),
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  Text(
                                    "En ligne",
                                    style: GoogleFonts.outfit(
                                      fontSize: 13,
                                      fontWeight: FontWeight.w700,
                                      color: const Color(0xFF15803D),
                                    ),
                                  ),
                                  const SizedBox(width: 6),
                                  Text(
                                    "• session active",
                                    style: GoogleFonts.outfit(
                                      fontSize: 12,
                                      color: const Color(0xFF94A3B8),
                                    ),
                                  ),
                                ],
                              );
                            },
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
        ),
      ),
    );
  }

  Widget _profileFallback(bool failed) {
    return Row(
      children: [
        Icon(
          failed ? Icons.cloud_off_rounded : Icons.person_outline_rounded,
          size: 40,
          color: const Color(0xFF94A3B8),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: Text(
            failed
                ? "Profil indisponible. Tirez pour actualiser."
                : "Chargement du profil…",
            style: GoogleFonts.outfit(
              fontSize: 14,
              color: const Color(0xFF64748B),
            ),
          ),
        ),
      ],
    );
  }

  Widget _skeleton() {
    return Row(
      children: [
        Container(
          width: 56,
          height: 56,
          decoration: BoxDecoration(
            color: const Color(0xFFE2E8F0),
            borderRadius: BorderRadius.circular(16),
          ),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                height: 16,
                width: 160,
                decoration: BoxDecoration(
                  color: const Color(0xFFE2E8F0),
                  borderRadius: BorderRadius.circular(6),
                ),
              ),
              const SizedBox(height: 8),
              Container(
                height: 12,
                width: 100,
                decoration: BoxDecoration(
                  color: const Color(0xFFF1F5F9),
                  borderRadius: BorderRadius.circular(6),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

Widget _initialsAvatar(AgentProfile profile) {
  return ColoredBox(
    color: const Color(0xFFEEF2FF),
    child: Center(
      child: Text(
        profile.initials,
        style: GoogleFonts.outfit(
          fontSize: 18,
          fontWeight: FontWeight.w800,
          color: const Color(0xFF4338CA),
        ),
      ),
    ),
  );
}

class _AvatarPulse extends StatelessWidget {
  const _AvatarPulse({
    required this.pulse,
    required this.profile,
    required this.photoUrl,
  });

  final Animation<double> pulse;
  final AgentProfile profile;
  final String? photoUrl;

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: pulse,
      builder: (context, _) {
        return Container(
          padding: const EdgeInsets.all(2.5),
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: SweepGradient(
              colors: [
                const Color(0xFF6366F1),
                const Color(0xFF22D3EE),
                const Color(0xFFA78BFA),
                const Color(0xFF6366F1),
              ],
              transform: GradientRotation(pulse.value * 3.14159),
            ),
          ),
          child: ClipOval(
            child: SizedBox(
              width: 56,
              height: 56,
              child: photoUrl != null
                  ? Image.network(
                      photoUrl!,
                      fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) => _initialsAvatar(profile),
                    )
                  : _initialsAvatar(profile),
            ),
          ),
        );
      },
    );
  }
}
