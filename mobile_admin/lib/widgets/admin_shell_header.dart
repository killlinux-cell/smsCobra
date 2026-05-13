import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../models/admin_profile.dart';
import '../theme/cobra_admin_theme.dart';

class AdminBrandHeader extends StatelessWidget {
  const AdminBrandHeader({
    super.key,
    required this.onSync,
    required this.onLogout,
  });

  final VoidCallback onSync;
  final VoidCallback onLogout;

  @override
  Widget build(BuildContext context) {
    final top = MediaQuery.paddingOf(context).top;
    return Container(
      width: double.infinity,
      padding: EdgeInsets.fromLTRB(20, top + 8, 12, 18),
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: CobraAdminColors.headerGradient,
        ),
      ),
      child: Row(
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
                        color: Colors.white.withAlpha(40),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: const Icon(
                        Icons.admin_panel_settings_rounded,
                        color: CobraAdminColors.brandIcon,
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
                          Text(
                            "Admin",
                            style: GoogleFonts.outfit(
                              fontSize: 15,
                              fontWeight: FontWeight.w500,
                              color: Colors.white.withAlpha(220),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                  decoration: BoxDecoration(
                    color: Colors.black.withAlpha(35),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: Colors.white.withAlpha(50)),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.insights_rounded, size: 16, color: CobraAdminColors.brandIcon),
                      const SizedBox(width: 6),
                      Text(
                        "Supervision terrain",
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
              _RoundHeaderBtn(
                icon: Icons.sync_rounded,
                tooltip: "Actualiser",
                onPressed: onSync,
              ),
              const SizedBox(height: 6),
              _RoundHeaderBtn(
                icon: Icons.logout_rounded,
                tooltip: "Déconnexion",
                onPressed: onLogout,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _RoundHeaderBtn extends StatelessWidget {
  const _RoundHeaderBtn({
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

class AdminProfileCard extends StatelessWidget {
  const AdminProfileCard({
    super.key,
    required this.profile,
    required this.pulse,
    required this.photoUrl,
    this.loading = false,
    this.loadFailed = false,
  });

  final AdminProfile? profile;
  final Animation<double> pulse;
  final String? photoUrl;
  final bool loading;
  final bool loadFailed;

  @override
  Widget build(BuildContext context) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: const Duration(milliseconds: 480),
      curve: Curves.easeOutCubic,
      builder: (context, t, child) {
        return Opacity(
          opacity: t,
          child: Transform.translate(
            offset: Offset(0, 14 * (1 - t)),
            child: child,
          ),
        );
      },
      child: Material(
        elevation: 8,
        shadowColor: CobraAdminColors.indigo.withAlpha(90),
        borderRadius: BorderRadius.circular(20),
        color: Colors.white,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          child: loading
              ? _skeleton()
              : profile == null
                  ? _fallback(loadFailed)
                  : Row(
                      children: [
                        _AdminAvatarPulse(
                          pulse: pulse,
                          profile: profile!,
                          photoUrl: photoUrl,
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                profile!.displayName,
                                style: GoogleFonts.outfit(
                                  fontSize: 17,
                                  fontWeight: FontWeight.w700,
                                  color: CobraAdminColors.ink,
                                ),
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                              ),
                              const SizedBox(height: 4),
                              Row(
                                children: [
                                  Icon(Icons.badge_outlined, size: 15, color: CobraAdminColors.indigo),
                                  const SizedBox(width: 4),
                                  Expanded(
                                    child: Text(
                                      profile!.matricule,
                                      style: GoogleFonts.outfit(
                                        fontSize: 13,
                                        fontWeight: FontWeight.w600,
                                        color: const Color(0xFF64748B),
                                      ),
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 4),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                decoration: BoxDecoration(
                                  color: CobraAdminColors.indigo.withAlpha(28),
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: Text(
                                  profile!.roleLabel,
                                  style: GoogleFonts.outfit(
                                    fontSize: 11,
                                    fontWeight: FontWeight.w700,
                                    color: CobraAdminColors.indigo,
                                  ),
                                ),
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
                                            color: CobraAdminColors.success,
                                            boxShadow: [
                                              BoxShadow(
                                                color: CobraAdminColors.success
                                                    .withAlpha((110 * pulse.value).round()),
                                                blurRadius: 8 * pulse.value,
                                                spreadRadius: 1,
                                              ),
                                            ],
                                          ),
                                        ),
                                      ),
                                      const SizedBox(width: 8),
                                      Text(
                                        "Connecté",
                                        style: GoogleFonts.outfit(
                                          fontSize: 13,
                                          fontWeight: FontWeight.w700,
                                          color: CobraAdminColors.success,
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

  Widget _fallback(bool failed) {
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
                ? "Profil indisponible. Actualisez depuis le bouton en haut à droite."
                : "Chargement du profil…",
            style: GoogleFonts.outfit(fontSize: 14, color: const Color(0xFF64748B)),
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

class _AdminAvatarPulse extends StatelessWidget {
  const _AdminAvatarPulse({
    required this.pulse,
    required this.profile,
    required this.photoUrl,
  });

  final Animation<double> pulse;
  final AdminProfile profile;
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
              colors: const [
                Color(0xFF7C3AED),
                Color(0xFFF59E0B),
                Color(0xFFD946EF),
                Color(0xFF7C3AED),
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
                      errorBuilder: (_, __, ___) => _initials(profile),
                    )
                  : _initials(profile),
            ),
          ),
        );
      },
    );
  }

  static Widget _initials(AdminProfile profile) {
    return ColoredBox(
      color: const Color(0xFFF3E8FF),
      child: Center(
        child: Text(
          profile.initials,
          style: GoogleFonts.outfit(
            fontSize: 18,
            fontWeight: FontWeight.w800,
            color: CobraAdminColors.indigo,
          ),
        ),
      ),
    );
  }
}
