import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

import '../models/admin_profile.dart';

/// Session expirée : access + refresh invalides ou absents.
class AdminSessionExpiredException implements Exception {
  @override
  String toString() => 'Session expirée. Reconnectez-vous.';
}

class AdminApi {
  /// Téléphone réel : `--dart-define=API_BASE=http://<IP_PC>:8000` (voir TEST_DEVICE.txt).
  static const apiBase = String.fromEnvironment(
    "API_BASE",
    defaultValue: "http://192.168.1.64:8000",
  );

  final _storage = const FlutterSecureStorage();

  Future<String?> getAccessToken() => _storage.read(key: "access_token");

  Map<String, String> get _jsonHeaders => {"Content-Type": "application/json"};

  Future<Map<String, String>> _authHeaders() async {
    final t = await getAccessToken();
    return {
      "Content-Type": "application/json",
      if (t != null && t.isNotEmpty) "Authorization": "Bearer $t",
    };
  }

  /// Demande un nouvel access (et refresh si rotation côté serveur).
  Future<bool> _tryRefreshAccessToken() async {
    final refresh = await _storage.read(key: "refresh_token");
    if (refresh == null || refresh.isEmpty) return false;
    final uri = Uri.parse("$apiBase/api/v1/auth/refresh");
    try {
      final resp = await http.post(
        uri,
        headers: _jsonHeaders,
        body: jsonEncode({"refresh": refresh}),
      );
      if (resp.statusCode != 200) return false;
      final data = jsonDecode(resp.body) as Map<String, dynamic>;
      final access = data["access"] as String?;
      if (access == null || access.isEmpty) return false;
      await _storage.write(key: "access_token", value: access);
      final newRefresh = data["refresh"] as String?;
      if (newRefresh != null && newRefresh.isNotEmpty) {
        await _storage.write(key: "refresh_token", value: newRefresh);
      }
      return true;
    } catch (_) {
      return false;
    }
  }

  /// GET avec renouvellement automatique du JWT si 401.
  Future<http.Response> _authGet(Uri uri) async {
    var headers = await _authHeaders();
    var resp = await http.get(uri, headers: headers);
    if (resp.statusCode == 401 && await _tryRefreshAccessToken()) {
      headers = await _authHeaders();
      resp = await http.get(uri, headers: headers);
    }
    return resp;
  }

  /// POST avec renouvellement automatique du JWT si 401.
  Future<http.Response> _authPost(Uri uri, {String? body}) async {
    var headers = await _authHeaders();
    var resp = await http.post(uri, headers: headers, body: body);
    if (resp.statusCode == 401 && await _tryRefreshAccessToken()) {
      headers = await _authHeaders();
      resp = await http.post(uri, headers: headers, body: body);
    }
    return resp;
  }

  /// PATCH avec renouvellement automatique du JWT si 401.
  Future<http.Response> _authPatch(Uri uri, {String? body}) async {
    var headers = await _authHeaders();
    var resp = await http.patch(uri, headers: headers, body: body);
    if (resp.statusCode == 401 && await _tryRefreshAccessToken()) {
      headers = await _authHeaders();
      resp = await http.patch(uri, headers: headers, body: body);
    }
    return resp;
  }

  Future<void> login(String username, String password) async {
    final uri = Uri.parse("$apiBase/api/v1/auth/login");
    final resp = await http.post(
      uri,
      headers: _jsonHeaders,
      body: jsonEncode({"username": username, "password": password}),
    );
    if (resp.statusCode != 200) throw Exception("login_failed");
    final data = jsonDecode(resp.body) as Map<String, dynamic>;
    await _storage.write(
      key: "access_token",
      value: data["access"] as String? ?? "",
    );
    await _storage.write(
      key: "refresh_token",
      value: data["refresh"] as String? ?? "",
    );
  }

  Future<void> logout() async {
    await _storage.delete(key: "access_token");
    await _storage.delete(key: "refresh_token");
  }

  String? resolveMediaUrl(String? path) {
    if (path == null || path.isEmpty) return null;
    if (path.startsWith("http://") || path.startsWith("https://")) return path;
    final base = apiBase.replaceAll(RegExp(r"/$"), "");
    final p = path.startsWith("/") ? path : "/$path";
    return "$base$p";
  }

  Future<AdminProfile> fetchMe() async {
    final uri = Uri.parse("$apiBase/api/v1/me");
    final resp = await _authGet(uri);
    if (resp.statusCode == 401) throw AdminSessionExpiredException();
    if (resp.statusCode != 200) throw Exception("me_failed");
    final m = jsonDecode(resp.body) as Map<String, dynamic>;
    final p = AdminProfile.fromJson(m);
    if (p == null || p.username.isEmpty) throw Exception("me_invalid");
    return p;
  }

  Future<void> registerFcmToken(String fcmToken) async {
    final headers = await _authHeaders();
    if (!headers.containsKey("Authorization")) return;
    final uri = Uri.parse("$apiBase/api/v1/me/fcm-token");
    var resp = await http.post(
      uri,
      headers: headers,
      body: jsonEncode({"fcm_token": fcmToken}),
    );
    if (resp.statusCode == 401 && await _tryRefreshAccessToken()) {
      resp = await _authPost(uri, body: jsonEncode({"fcm_token": fcmToken}));
    }
    if (resp.statusCode == 401) throw AdminSessionExpiredException();
    if (resp.statusCode != 200) throw Exception("fcm_failed");
  }

  Future<Map<String, dynamic>> fetchLiveStatus() async {
    final uri = Uri.parse("$apiBase/api/v1/admin/alerts/live-status");
    final resp = await _authGet(uri);
    if (resp.statusCode == 401) throw AdminSessionExpiredException();
    if (resp.statusCode != 200) throw Exception("status_failed");
    return jsonDecode(resp.body) as Map<String, dynamic>;
  }

  Future<List<dynamic>> fetchAlerts({String? status}) async {
    var uri = Uri.parse("$apiBase/api/v1/admin/alerts/");
    if (status != null && status.isNotEmpty) {
      uri = uri.replace(queryParameters: {"status": status});
    }
    final resp = await _authGet(uri);
    if (resp.statusCode == 401) throw AdminSessionExpiredException();
    if (resp.statusCode != 200) throw Exception("alerts_failed");
    final decoded = jsonDecode(resp.body);
    if (decoded is List) return decoded;
    return [];
  }

  Future<void> ackAlert(int alertId) async {
    final uri = Uri.parse("$apiBase/api/v1/admin/alerts/$alertId/ack");
    final resp = await _authPost(uri);
    if (resp.statusCode == 401) throw AdminSessionExpiredException();
    if (resp.statusCode != 200) throw Exception("ack_failed");
  }

  Future<List<dynamic>> fetchTodayAssignments() async {
    final uri = Uri.parse("$apiBase/api/v1/admin/alerts/today-assignments");
    final resp = await _authGet(uri);
    if (resp.statusCode == 401) throw AdminSessionExpiredException();
    if (resp.statusCode != 200) throw Exception("assignments_failed");
    final decoded = jsonDecode(resp.body);
    if (decoded is List) return decoded;
    return [];
  }

  Future<List<dynamic>> fetchVigiles() async {
    final uri = Uri.parse("$apiBase/api/v1/admin/alerts/vigiles");
    final resp = await _authGet(uri);
    if (resp.statusCode == 401) throw AdminSessionExpiredException();
    if (resp.statusCode != 200) throw Exception("vigiles_failed");
    final decoded = jsonDecode(resp.body);
    if (decoded is List) return decoded;
    return [];
  }

  Future<List<dynamic>> fetchSites() async {
    final uri = Uri.parse("$apiBase/api/v1/admin/sites/");
    final resp = await _authGet(uri);
    if (resp.statusCode == 401) throw AdminSessionExpiredException();
    if (resp.statusCode != 200) throw Exception("sites_failed");
    final decoded = jsonDecode(resp.body);
    if (decoded is List) return decoded;
    return [];
  }

  Future<void> createSite(Map<String, dynamic> payload) async {
    final uri = Uri.parse("$apiBase/api/v1/admin/sites/");
    final resp = await _authPost(uri, body: jsonEncode(payload));
    if (resp.statusCode == 401) throw AdminSessionExpiredException();
    if (resp.statusCode != 201) throw Exception("site_create_failed");
  }

  Future<void> updateSite(int siteId, Map<String, dynamic> payload) async {
    final uri = Uri.parse("$apiBase/api/v1/admin/sites/$siteId/");
    final resp = await _authPatch(uri, body: jsonEncode(payload));
    if (resp.statusCode == 401) throw AdminSessionExpiredException();
    if (resp.statusCode != 200) throw Exception("site_update_failed");
  }

  Future<void> createVigileMultipart({
    String? username,
    required String firstName,
    required String lastName,
    required String email,
    required String phoneNumber,
    String? domicile,
    required String photoPath,
  }) async {
    Future<http.StreamedResponse> sendRequest() async {
      final headers = await _authHeaders();
      final req = http.MultipartRequest(
        "POST",
        Uri.parse("$apiBase/api/v1/admin/vigiles/"),
      );
      final auth = headers["Authorization"];
      if (auth != null && auth.isNotEmpty) req.headers["Authorization"] = auth;
      if (username != null && username.trim().isNotEmpty) {
        req.fields["username"] = username.trim();
      }
      if (firstName.trim().isNotEmpty) {
        req.fields["first_name"] = firstName.trim();
      }
      if (lastName.trim().isNotEmpty) req.fields["last_name"] = lastName.trim();
      if (email.trim().isNotEmpty) req.fields["email"] = email.trim();
      if (phoneNumber.trim().isNotEmpty) {
        req.fields["phone_number"] = phoneNumber.trim();
      }
      if (domicile != null && domicile.trim().isNotEmpty) {
        req.fields["domicile"] = domicile.trim();
      }
      req.files.add(
        await http.MultipartFile.fromPath("profile_photo", photoPath),
      );
      return req.send();
    }

    var streamed = await sendRequest();
    if (streamed.statusCode == 401 && await _tryRefreshAccessToken()) {
      streamed = await sendRequest();
    }
    if (streamed.statusCode == 401) throw AdminSessionExpiredException();
    if (streamed.statusCode != 201) {
      throw Exception("vigile_create_failed");
    }
  }

  Future<void> dispatchReplacement({
    required int assignmentId,
    required int replacementGuardId,
  }) async {
    final uri = Uri.parse("$apiBase/api/v1/admin/alerts/dispatch");
    final resp = await _authPost(
      uri,
      body: jsonEncode({
        "assignment_id": assignmentId,
        "replacement_guard_id": replacementGuardId,
      }),
    );
    if (resp.statusCode == 401) throw AdminSessionExpiredException();
    if (resp.statusCode != 200) throw Exception("dispatch_failed");
  }

  Future<List<dynamic>> fetchActivityFeed({int limit = 60}) async {
    final uri = Uri.parse(
      "$apiBase/api/v1/admin/reports/activity/",
    ).replace(queryParameters: {"limit": "$limit"});
    final resp = await _authGet(uri);
    if (resp.statusCode == 401) throw AdminSessionExpiredException();
    if (resp.statusCode != 200) throw Exception("activity_feed_failed");
    final decoded = jsonDecode(resp.body);
    if (decoded is List) return decoded;
    return [];
  }

  Future<List<dynamic>> fetchReports({int limit = 40}) async {
    final uri = Uri.parse("$apiBase/api/v1/admin/reports/");
    final resp = await _authGet(uri);
    if (resp.statusCode == 401) throw AdminSessionExpiredException();
    if (resp.statusCode != 200) throw Exception("reports_failed");
    final decoded = jsonDecode(resp.body);
    if (decoded is List) {
      final list = decoded;
      if (list.length <= limit) return list;
      return list.sublist(0, limit);
    }
    return [];
  }
}
