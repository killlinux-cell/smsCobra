import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'pages/admin_shell.dart';
import 'pages/login_page.dart';
import 'services/admin_api.dart';
import 'theme/cobra_admin_theme.dart';

@pragma('vm:entry-point')
Future<void> firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  await Firebase.initializeApp();
}

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  var firebaseOk = false;
  try {
    await Firebase.initializeApp();
    FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler);
    firebaseOk = true;
  } catch (_) {
    firebaseOk = false;
  }
  runApp(CobraAdminBootstrap(firebaseConfigured: firebaseOk));
}

class CobraAdminBootstrap extends StatefulWidget {
  const CobraAdminBootstrap({super.key, required this.firebaseConfigured});

  final bool firebaseConfigured;

  @override
  State<CobraAdminBootstrap> createState() => _CobraAdminBootstrapState();
}

class _CobraAdminBootstrapState extends State<CobraAdminBootstrap> {
  final _api = AdminApi();
  final _storage = const FlutterSecureStorage();
  bool _loading = true;
  String? _token;

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    final t = await _storage.read(key: "access_token");
    if (!mounted) return;
    setState(() {
      _token = t;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SMS Admin',
      debugShowCheckedModeBanner: false,
      theme: cobraAdminTheme(),
      home: _loading
          ? Scaffold(
              backgroundColor: Colors.black,
              body: Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Image.asset(
                      'assets/images/sms_logo.png',
                      width: 220,
                      fit: BoxFit.contain,
                    ),
                    const SizedBox(height: 28),
                    const SizedBox(
                      width: 32,
                      height: 32,
                      child: CircularProgressIndicator(
                        strokeWidth: 2.5,
                        color: Color(0xFFE31E24),
                      ),
                    ),
                  ],
                ),
              ),
            )
          : (_token != null && _token!.isNotEmpty)
              ? AdminShell(
                  api: _api,
                  firebaseConfigured: widget.firebaseConfigured,
                )
              : LoginPage(
                  api: _api,
                  firebaseConfigured: widget.firebaseConfigured,
                ),
    );
  }
}
