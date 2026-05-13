import 'package:flutter/material.dart';

class ModernActionButton extends StatelessWidget {
  const ModernActionButton({
    super.key,
    required this.label,
    required this.icon,
    required this.enabled,
    required this.onTap,
    required this.colors,
  });

  final String label;
  final IconData icon;
  final bool enabled;
  final VoidCallback onTap;
  final List<Color> colors;

  @override
  Widget build(BuildContext context) {
    final fgColor = enabled ? Colors.white : const Color(0xFF334155);
    return Opacity(
      opacity: enabled ? 1 : 0.45,
      child: TweenAnimationBuilder<double>(
        tween: Tween<double>(begin: 0.98, end: enabled ? 1 : 0.98),
        duration: const Duration(milliseconds: 220),
        builder: (context, scale, child) {
          return Transform.scale(scale: scale, child: child);
        },
        child: InkWell(
          borderRadius: BorderRadius.circular(18),
          onTap: enabled ? onTap : null,
          child: Ink(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(18),
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: enabled
                    ? colors
                    : [const Color(0xFF94A3B8), const Color(0xFFCBD5E1)],
              ),
              boxShadow: [
                BoxShadow(
                  color: (enabled ? colors.first : const Color(0xFF64748B))
                      .withAlpha(60),
                  blurRadius: 14,
                  offset: const Offset(0, 8),
                ),
              ],
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(icon, color: fgColor),
                const SizedBox(width: 8),
                Text(
                  label,
                  style: TextStyle(
                    color: fgColor,
                    fontWeight: FontWeight.w800,
                    fontSize: 15,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

