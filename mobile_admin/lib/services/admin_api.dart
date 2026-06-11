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
    defaultValue: "https://smsapp24.com",
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

  /// DELETE avec renouvellement automatique du JWT si 401.
  Future<http.Response> _authDelete(Uri uri) async {
    var headers = await _authHeaders();
    var resp = await http.delete(uri, headers: headers);
    if (resp.statusCode == 401 && await _tryRefreshAccessToken()) {
      headers = await _authHeaders();
      resp = await http.delete(uri, headers: headers);
    }
    return resp;
  }

  String? _extractApiErrorMessage(String body) {
    try {
      final decoded = jsonDecode(body);
      if (decoded is! Map) return null;
      final detail = decoded['detail'];
      if (detail != null && detail.toString().isNotEmpty) {
        return detail.toString();
      }
      for (final value in decoded.values) {
        if (value is List && value.isNotEmpty) {
          return value.first.toString();
        }
        if (value is String && value.isNotEmpty) return value;
      }
    } catch (_) {}
    return null;
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

  Future<Map<String, dynamic>> fetchVigile(int vigileId) async {
    final uri = Uri.parse("$apiBase/api/v1/admin/vigiles/$vigileId/");
    final resp = await _authGet(uri);
    if (resp.statusCode == 401) throw AdminSessionExpiredException();
    if (resp.statusCode != 200) throw Exception("vigile_failed");
    return jsonDecode(resp.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> fetchSite(int siteId) async {
    final uri = Uri.parse("$apiBase/api/v1/admin/sites/$siteId/");
    final resp = await _authGet(uri);
    if (resp.statusCode == 401) throw AdminSessionExpiredException();
    if (resp.statusCode != 200) throw Exception("site_failed");
    return jsonDecode(resp.body) as Map<String, dynamic>;
  }

  Future<List<dynamic>> fetchReplacementNeeded() async {
    final uri = Uri.parse("$apiBase/api/v1/admin/alerts/replacement-needed");
    final resp = await _authGet(uri);
    if (resp.statusCode == 401) throw AdminSessionExpiredException();
    if (resp.statusCode != 200) throw Exception("replacement_needed_failed");
    final decoded = jsonDecode(resp.body);
    if (decoded is List) return decoded;
    return [];
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

  /// Vigiles disponibles pour remplacer sur une affectation (libres sur le créneau).
  Future<List<dynamic>> fetchDispatchCandidates(
    int assignmentId, {
    bool includeBusy = false,
  }) async {
    final params = <String, String>{"assignment_id": "$assignmentId"};
    if (includeBusy) params["include_busy"] = "1";
    final uri = Uri.parse(
      "$apiBase/api/v1/admin/alerts/dispatch-candidates",
    ).replace(queryParameters: params);
    final resp = await _authGet(uri);
    if (resp.statusCode == 401) throw AdminSessionExpiredException();
    if (resp.statusCode != 200) throw Exception("dispatch_candidates_failed");
    final decoded = jsonDecode(resp.body);
    if (decoded is List) return decoded;
    return [];
  }

  Future<List<dynamic>> fetchVigiles() async {
    final uri = Uri.parse("$apiBase/api/v1/admin/vigiles/");
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

  Future<List<dynamic>> fetchAssignments({
    int? siteId,
    String? status,
    String? dateFrom,
    String? dateTo,
  }) async {
    final params = <String, String>{};
    if (siteId != null) params['site'] = '$siteId';
    if (status != null && status.isNotEmpty) params['status'] = status;
    if (dateFrom != null && dateFrom.isNotEmpty) params['date_from'] = dateFrom;
    if (dateTo != null && dateTo.isNotEmpty) params['date_to'] = dateTo;
    final uri = Uri.parse("$apiBase/api/v1/admin/assignments/").replace(
      queryParameters: params.isEmpty ? null : params,
    );
    final resp = await _authGet(uri);
    if (resp.statusCode == 401) throw AdminSessionExpiredException();
    if (resp.statusCode != 200) throw Exception("assignments_list_failed");
    final decoded = jsonDecode(resp.body);
    if (decoded is List) return decoded;
    return [];
  }

  Future<Map<String, dynamic>> fetchAssignment(int assignmentId) async {
    final uri = Uri.parse("$apiBase/api/v1/admin/assignments/$assignmentId/");
    final resp = await _authGet(uri);
    if (resp.statusCode == 401) throw AdminSessionExpiredException();
    if (resp.statusCode != 200) throw Exception("assignment_failed");
    return jsonDecode(resp.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> createAssignment(Map<String, dynamic> payload) async {
    final uri = Uri.parse("$apiBase/api/v1/admin/assignments/");
    final resp = await _authPost(uri, body: jsonEncode(payload));
    if (resp.statusCode == 401) throw AdminSessionExpiredException();
    if (resp.statusCode != 201) {
      throw Exception(_extractApiErrorMessage(resp.body) ?? 'assignment_create_failed');
    }
    return jsonDecode(resp.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> updateAssignment(
    int assignmentId,
    Map<String, dynamic> payload,
  ) async {
    final uri = Uri.parse("$apiBase/api/v1/admin/assignments/$assignmentId/");
    final resp = await _authPatch(uri, body: jsonEncode(payload));
    if (resp.statusCode == 401) throw AdminSessionExpiredException();
    if (resp.statusCode != 200) {
      throw Exception(_extractApiErrorMessage(resp.body) ?? 'assignment_update_failed');
    }
    return jsonDecode(resp.body) as Map<String, dynamic>;
  }

  Future<void> deleteAssignment(int assignmentId) async {
    final uri = Uri.parse("$apiBase/api/v1/admin/assignments/$assignmentId/");
    final resp = await _authDelete(uri);
    if (resp.statusCode == 401) throw AdminSessionExpiredException();
    if (resp.statusCode != 204 && resp.statusCode != 200) {
      throw Exception(_extractApiErrorMessage(resp.body) ?? 'assignment_delete_failed');
    }
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
    required String photoPath,
    String? username,
    String? firstName,
    String? lastName,
    String? email,
    String? phoneNumber,
    String? domicile,
    String? aval,
    String? dateIntegration,
    String? heightCm,
    String? educationLevel,
    String? idDocumentPath,
    String? idDocumentVersoPath,
  }) async {
    Future<http.StreamedResponse> sendRequest() async {
      final headers = await _authHeaders();
      final req = http.MultipartRequest(
        "POST",
        Uri.parse("$apiBase/api/v1/admin/vigiles/"),
      );
      final auth = headers["Authorization"];
      if (auth != null && auth.isNotEmpty) req.headers["Authorization"] = auth;

      void field(String key, String? value) {
        if (value != null && value.trim().isNotEmpty) {
          req.fields[key] = value.trim();
        }
      }

      field("username", username);
      field("first_name", firstName);
      field("last_name", lastName);
      field("email", email);
      field("phone_number", phoneNumber);
      field("domicile", domicile);
      field("aval", aval);
      field("date_integration", dateIntegration);
      field("height_cm", heightCm);
      field("education_level", educationLevel);

      req.files.add(
        await http.MultipartFile.fromPath("profile_photo", photoPath),
      );
      if (idDocumentPath != null && idDocumentPath.isNotEmpty) {
        req.files.add(
          await http.MultipartFile.fromPath("id_document", idDocumentPath),
        );
      }
      if (idDocumentVersoPath != null && idDocumentVersoPath.isNotEmpty) {
        req.files.add(
          await http.MultipartFile.fromPath(
            "id_document_verso",
            idDocumentVersoPath,
          ),
        );
      }
      return req.send();
    }

    var streamed = await sendRequest();
    if (streamed.statusCode == 401 && await _tryRefreshAccessToken()) {
      streamed = await sendRequest();
    }
    if (streamed.statusCode == 401) throw AdminSessionExpiredException();
    if (streamed.statusCode != 201) {
      final body = await streamed.stream.bytesToString();
      String? message;
      try {
        final decoded = jsonDecode(body);
        if (decoded is Map) {
          final photoErrors = decoded['profile_photo'];
          if (photoErrors is List && photoErrors.isNotEmpty) {
            message = photoErrors.first.toString();
          } else {
            final detail = decoded['detail'];
            if (detail != null && detail.toString().isNotEmpty) {
              message = detail.toString();
            }
          }
        }
      } catch (_) {
        // corps non JSON
      }
      throw Exception(message ?? 'vigile_create_failed');
    }
  }

  Future<String> dispatchReplacement({
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
    if (resp.statusCode != 200) {
      try {
        final decoded = jsonDecode(resp.body);
        if (decoded is Map && decoded['detail'] != null) {
          throw Exception(decoded['detail'].toString());
        }
      } catch (e) {
        if (e is Exception && e.toString().contains('Exception:')) rethrow;
      }
      throw Exception("dispatch_failed");
    }
    try {
      final decoded = jsonDecode(resp.body) as Map<String, dynamic>;
      return decoded['detail']?.toString() ?? 'Remplacement enregistré.';
    } catch (_) {
      return 'Remplacement enregistré.';
    }
  }

  Future<Map<String, dynamic>> updateVigileMultipart({
    required int vigileId,
    required Map<String, String> fields,
    String? photoPath,
  }) async {
    Future<http.StreamedResponse> sendRequest() async {
      final headers = await _authHeaders();
      final req = http.MultipartRequest(
        "PATCH",
        Uri.parse("$apiBase/api/v1/admin/vigiles/$vigileId/"),
      );
      final auth = headers["Authorization"];
      if (auth != null && auth.isNotEmpty) req.headers["Authorization"] = auth;
      req.fields.addAll(fields);
      if (photoPath != null && photoPath.isNotEmpty) {
        req.files.add(
          await http.MultipartFile.fromPath("profile_photo", photoPath),
        );
      }
      return req.send();
    }

    var streamed = await sendRequest();
    if (streamed.statusCode == 401 && await _tryRefreshAccessToken()) {
      streamed = await sendRequest();
    }
    if (streamed.statusCode == 401) throw AdminSessionExpiredException();
    final body = await streamed.stream.bytesToString();
    if (streamed.statusCode != 200) {
      String? message;
      try {
        final decoded = jsonDecode(body);
        if (decoded is Map) {
          final photoErrors = decoded['profile_photo'];
          if (photoErrors is List && photoErrors.isNotEmpty) {
            message = photoErrors.first.toString();
          } else {
            final detail = decoded['detail'];
            if (detail != null) message = detail.toString();
          }
        }
      } catch (_) {}
      throw Exception(message ?? 'vigile_update_failed');
    }
    return jsonDecode(body) as Map<String, dynamic>;
  }

  Future<List<dynamic>> fetchActivityFeed({int limit = 60, int? siteId}) async {
    final params = <String, String>{"limit": "$limit"};
    if (siteId != null) params['site'] = '$siteId';
    final uri = Uri.parse(
      "$apiBase/api/v1/admin/reports/activity/",
    ).replace(queryParameters: params);
    final resp = await _authGet(uri);
    if (resp.statusCode == 401) throw AdminSessionExpiredException();
    if (resp.statusCode != 200) throw Exception("activity_feed_failed");
    final decoded = jsonDecode(resp.body);
    if (decoded is List) return decoded;
    return [];
  }

  Future<List<dynamic>> fetchReports({
    int limit = 40,
    String? date,
    String? month,
    int? siteId,
    int? guardId,
  }) async {
    final params = <String, String>{};
    if (date != null && date.isNotEmpty) params['date'] = date;
    if (month != null && month.isNotEmpty) params['month'] = month;
    if (siteId != null) params['site'] = '$siteId';
    if (guardId != null) params['guard'] = '$guardId';
    final uri = Uri.parse("$apiBase/api/v1/admin/reports/").replace(
      queryParameters: params.isEmpty ? null : params,
    );
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

  /// Passages contrôleurs : historique + couverture sites (superviseur).
  Future<Map<String, dynamic>> fetchControllerVisits({
    String? date,
    String? month,
    int? siteId,
  }) async {
    final params = <String, String>{};
    if (date != null && date.isNotEmpty) params['date'] = date;
    if (month != null && month.isNotEmpty) params['month'] = month;
    if (siteId != null) params['site'] = '$siteId';
    final uri = Uri.parse(
      "$apiBase/api/v1/admin/reports/controller-visits/",
    ).replace(queryParameters: params.isEmpty ? null : params);
    final resp = await _authGet(uri);
    if (resp.statusCode == 401) throw AdminSessionExpiredException();
    if (resp.statusCode != 200) throw Exception("controller_visits_failed");
    final decoded = jsonDecode(resp.body);
    if (decoded is Map<String, dynamic>) return decoded;
    return {};
  }
}
