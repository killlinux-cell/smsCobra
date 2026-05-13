import 'package:flutter/material.dart';

import '../pages/agent_home_page.dart';
import '../pages/login_page.dart';
import '../services/cobra_api.dart';

class BootstrapPage extends StatefulWidget {
  const BootstrapPage({super.key});

  @override
  State<BootstrapPage> createState() => _BootstrapPageState();
}

class _BootstrapPageState extends State<BootstrapPage> {
  final _api = CobraApi();
  bool _loading = true;
  bool _sessionOk = false;

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    var access = await _api.getAccessToken();
    final refresh = await _api.getRefreshToken();
    if ((access == null || access.isEmpty) &&
        refresh != null &&
        refresh.isNotEmpty) {
      await _api.tryRefreshAccessToken();
      access = await _api.getAccessToken();
    }

    if (access != null && access.isNotEmpty) {
      try {
        await _api.fetchMe();
        if (mounted) {
          setState(() {
            _sessionOk = true;
            _loading = false;
          });
        }
        return;
      } catch (_) {
        final refreshed = await _api.tryRefreshAccessToken();
        if (refreshed) {
          try {
            await _api.fetchMe();
            if (mounted) {
              setState(() {
                _sessionOk = true;
                _loading = false;
              });
            }
            return;
          } catch (_) {}
        }
        await _api.logout();
      }
    }

    if (!mounted) return;
    setState(() {
      _sessionOk = false;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return Scaffold(
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
      );
    }
    if (!_sessionOk) {
      return LoginPage(api: _api);
    }
    return AgentHomePage(api: _api);
  }
}
