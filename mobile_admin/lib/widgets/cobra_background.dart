import 'package:flutter/material.dart';

import '../theme/cobra_admin_theme.dart';

/// Fond dégradé + halos (même esprit que l’app agent).
class CobraAdminBackground extends StatelessWidget {
  const CobraAdminBackground({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Stack(
      fit: StackFit.expand,
      children: [
        Container(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                Color(0xFFF3E8FF),
                Color(0xFFFAF5FF),
                Color(0xFFFDF4FF),
              ],
            ),
          ),
        ),
        Positioned(
          top: -50,
          right: -35,
          child: Container(
            width: 200,
            height: 200,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: CobraAdminColors.indigo.withAlpha(28),
            ),
          ),
        ),
        Positioned(
          bottom: 80,
          left: -45,
          child: Container(
            width: 160,
            height: 160,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: const Color(0xFFEC4899).withAlpha(20),
            ),
          ),
        ),
        child,
      ],
    );
  }
}
