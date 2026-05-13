import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class CobraAdminColors {
  /// Texte principal (rouge très foncé / encre).
  static const ink = Color(0xFF1c0a0a);
  /// Fonds d’écran (rouge très pâle).
  static const surface = Color(0xFFFFF5F5);
  static const card = Color(0xE6FFFFFF);
  /// Marque, liens, barre de navigation (rouge SMS).
  static const indigo = Color(0xFFb91c1c);
  /// Boutons forts, accents chauds (ambre).
  static const accent = Color(0xFFF59E0B);
  static const danger = Color(0xFFDC2626);
  static const success = Color(0xFF059669);

  /// Bandeau haut / écran login.
  static const List<Color> headerGradient = [
    Color(0xFF450a0a),
    Color(0xFF991b1b),
    Color(0xFFb91c1c),
  ];

  /// Accent clair sur fond rouge (lisibilité).
  static const brandIcon = Color(0xFFE5E5E5);
}

ThemeData cobraAdminTheme() {
  final base = ColorScheme.fromSeed(
    seedColor: CobraAdminColors.indigo,
    brightness: Brightness.light,
    surface: CobraAdminColors.surface,
    primary: CobraAdminColors.indigo,
    secondary: CobraAdminColors.accent,
  );
  final textTheme = GoogleFonts.outfitTextTheme();
  return ThemeData(
    useMaterial3: true,
    colorScheme: base,
    textTheme: textTheme.apply(
      bodyColor: CobraAdminColors.ink,
      displayColor: CobraAdminColors.ink,
    ),
    scaffoldBackgroundColor: CobraAdminColors.surface,
    appBarTheme: const AppBarTheme(
      centerTitle: false,
      elevation: 0,
      scrolledUnderElevation: 0,
      backgroundColor: Colors.transparent,
      foregroundColor: CobraAdminColors.ink,
    ),
    navigationBarTheme: NavigationBarThemeData(
      indicatorColor: CobraAdminColors.indigo.withAlpha(45),
      labelTextStyle: WidgetStateProperty.resolveWith((s) {
        if (s.contains(WidgetState.selected)) {
          return const TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w700,
            color: CobraAdminColors.indigo,
          );
        }
        return const TextStyle(fontSize: 12, color: Color(0xFF64748B));
      }),
    ),
  );
}
