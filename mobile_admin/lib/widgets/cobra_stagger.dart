import 'package:flutter/material.dart';

/// Entrée en fondu + léger slide vertical, décalée par [index] sur [controller].
Widget cobraStaggerItem({
  required AnimationController controller,
  required int index,
  required Widget child,
  double step = 0.052,
  double window = 0.34,
}) {
  final start = (index * step).clamp(0.0, 0.76);
  final end = (start + window).clamp(0.06, 1.0);
  final anim = CurvedAnimation(
    parent: controller,
    curve: Interval(start, end, curve: Curves.easeOutCubic),
  );
  return FadeTransition(
    opacity: anim,
    child: SlideTransition(
      position: Tween<Offset>(
        begin: const Offset(0, 0.07),
        end: Offset.zero,
      ).animate(anim),
      child: child,
    ),
  );
}
