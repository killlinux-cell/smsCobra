import 'package:flutter/material.dart';
import '../bootstrap/bootstrap_page.dart';

class CobraAgentApp extends StatelessWidget {
  const CobraAgentApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SMS Agent',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF4F46E5),
          brightness: Brightness.light,
        ),
        useMaterial3: true,
        scaffoldBackgroundColor: const Color(0xFFF5F7FF),
        appBarTheme: const AppBarTheme(
          backgroundColor: Colors.transparent,
          surfaceTintColor: Colors.transparent,
          elevation: 0,
          foregroundColor: Color(0xFF111827),
          centerTitle: false,
        ),
        cardTheme: CardThemeData(
          color: Colors.white.withAlpha(235),
          elevation: 0,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
        ),
      ),
      themeMode: ThemeMode.light,
      home: const BootstrapPage(),
    );
  }
}

