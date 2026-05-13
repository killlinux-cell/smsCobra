import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

import '../models/agent_profile.dart';
import '../models/assignment.dart';

class EntrySite {
  final int id;
  final String name;
  const EntrySite({required this.id, required this.name});
}

class CobraApi {
  /// Émulateur Android : 10.0.2.2. Téléphone réel : même Wi‑Fi que le PC, ex.
  /// `flutter run --dart-define=API_BASE=http://192.168.1.42:8000` (IP = ipconfig).
  static const apiBase = String.fromEnvironment(
    "API_BASE",
    defaultValue: "http://192.168.1.64:8000",
  );
  final _storage = const FlutterSecureStorage();

  Future<String?> getAccessToken() => _storage.read(key: "access_token");

  Future<String?> getRefreshToken() => _storage.read(key: "refresh_token");

  /// URL absolue pour afficher une photo profil renvoyée par l’API (chemin relatif ou URL).
  String? resolveMediaUrl(String? path) {
    if (path == null || path.isEmpty) return null;
    if (path.startsWith("http://") || path.startsWith("https://")) return path;
    final base = apiBase.replaceAll(RegExp(r"/$"), "");
    final p = path.startsWith("/") ? path : "/$path";
    return "$base$p";
  }

  Future<AgentProfile> fetchMe() async {
    final token = await getAccessToken();
    final uri = Uri.parse("$apiBase/api/v1/me");
    final resp = await http.get(
      uri,
      headers: {"Authorization": "Bearer $token"},
    );
    if (resp.statusCode != 200) throw Exception("me_failed");
    final m = jsonDecode(resp.body) as Map<String, dynamic>;
    final p = AgentProfile.fromJson(m);
    if (p == null || p.username.isEmpty) throw Exception("me_invalid");
    return p;
  }

  Future<void> _storeJwtFromBody(String body) async {
    final data = jsonDecode(body) as Map<String, dynamic>;
    await _storage.write(
      key: "access_token",
      value: data["access"] as String? ?? "",
    );
    await _storage.write(
      key: "refresh_token",
      value: data["refresh"] as String? ?? "",
    );
  }

  /// Connexion classique (mot de passe) — utile pour tests / outils ; l’app vigile utilise [faceLogin].
  Future<void> login(String username, String password) async {
    final uri = Uri.parse("$apiBase/api/v1/auth/login");
    try {
      final resp = await http
          .post(
            uri,
            headers: {"Content-Type": "application/json"},
            body: jsonEncode({"username": username, "password": password}),
          )
          .timeout(const Duration(seconds: 25));
      if (resp.statusCode == 200) {
        await _storeJwtFromBody(resp.body);
        return;
      }
      if (resp.statusCode == 401) {
        throw Exception("login_bad_credentials");
      }
      throw Exception("login_http_${resp.statusCode}");
    } on SocketException {
      throw Exception("network_unreachable");
    } on TimeoutException {
      throw Exception("network_timeout");
    }
  }

  /// Connexion vigile : identifiant + selfie (sans mot de passe), comparé à la photo d’enrôlement.
  Future<void> faceLogin(String username, String selfiePath) async {
    final uri = Uri.parse("$apiBase/api/v1/auth/face-login");
    final req = http.MultipartRequest("POST", uri);
    req.fields["username"] = username.trim();
    req.files.add(
      await http.MultipartFile.fromPath(
        "selfie",
        selfiePath,
        filename: "face_login.jpg",
      ),
    );
    try {
      final streamed = await req.send().timeout(const Duration(seconds: 45));
      final resp = await http.Response.fromStream(streamed);
      if (resp.statusCode == 200) {
        await _storeJwtFromBody(resp.body);
        return;
      }
      String? detail;
      try {
        final decoded = jsonDecode(resp.body);
        if (decoded is Map<String, dynamic>) {
          final d = decoded["detail"];
          if (d is String) detail = d;
        }
      } catch (_) {}
      if (resp.statusCode == 401) {
        throw Exception(detail ?? "face_login_rejected");
      }
      throw Exception(detail ?? "face_login_http_${resp.statusCode}");
    } on SocketException {
      throw Exception("network_unreachable");
    } on TimeoutException {
      throw Exception("network_timeout");
    }
  }

  /// Connexion vigile sans identifiant: identification directe par visage.
  /// [siteId] optionnel : restreint les candidats à ce site (sinon tous les services récents).
  Future<String> faceIdentifyLogin(String selfiePath, {int? siteId}) async {
    final uri = Uri.parse("$apiBase/api/v1/auth/face-identify");
    final req = http.MultipartRequest("POST", uri);
    if (siteId != null && siteId > 0) {
      req.fields["site_id"] = siteId.toString();
    }
    req.files.add(
      await http.MultipartFile.fromPath(
        "selfie",
        selfiePath,
        filename: "face_identify.jpg",
      ),
    );
    try {
      final streamed = await req.send().timeout(const Duration(seconds: 45));
      final resp = await http.Response.fromStream(streamed);
      if (resp.statusCode == 200) {
        await _storeJwtFromBody(resp.body);
        final decoded = jsonDecode(resp.body) as Map<String, dynamic>;
        final username = (decoded["guard_username"] ?? "").toString();
        return username;
      }
      String? detail;
      try {
        final decoded = jsonDecode(resp.body);
        if (decoded is Map<String, dynamic>) {
          final d = decoded["detail"];
          if (d is String) detail = d;
        }
      } catch (_) {}
      throw Exception(detail ?? "face_identify_http_${resp.statusCode}");
    } on SocketException {
      throw Exception("network_unreachable");
    } on TimeoutException {
      throw Exception("network_timeout");
    }
  }

  Future<List<EntrySite>> fetchEntrySites() async {
    final uri = Uri.parse("$apiBase/api/v1/entry/sites");
    try {
      final resp = await http.get(uri).timeout(const Duration(seconds: 20));
      if (resp.statusCode != 200) throw Exception("entry_sites_http_${resp.statusCode}");
      final decoded = jsonDecode(resp.body);
      if (decoded is! List) return const [];
      return decoded
          .whereType<Map<String, dynamic>>()
          .map(
            (m) => EntrySite(
              id: (m["id"] as num?)?.toInt() ?? 0,
              name: (m["name"] ?? "").toString(),
            ),
          )
          .where((s) => s.id > 0 && s.name.isNotEmpty)
          .toList();
    } on SocketException {
      throw Exception("network_unreachable");
    } on TimeoutException {
      throw Exception("network_timeout");
    }
  }

  Future<String> controllerFaceCheckin({
    required int siteId,
    required String selfiePath,
    String deviceId = "mobile_agent",
  }) async {
    final uri = Uri.parse("$apiBase/api/v1/auth/controller-face-checkin");
    final req = http.MultipartRequest("POST", uri);
    req.fields["site_id"] = siteId.toString();
    req.fields["device_id"] = deviceId;
    req.files.add(
      await http.MultipartFile.fromPath(
        "selfie",
        selfiePath,
        filename: "controller_checkin.jpg",
      ),
    );
    try {
      final streamed = await req.send().timeout(const Duration(seconds: 45));
      final resp = await http.Response.fromStream(streamed);
      String? detail;
      Map<String, dynamic>? decoded;
      try {
        final j = jsonDecode(resp.body);
        if (j is Map<String, dynamic>) {
          decoded = j;
          final d = j["detail"];
          if (d is String) detail = d;
        }
      } catch (_) {}
      if (resp.statusCode == 200 || resp.statusCode == 201) {
        final name = (decoded?["controller_name"] ?? "").toString();
        final site = (decoded?["site_name"] ?? "").toString();
        final created = decoded?["created"] == true;
        if (name.isNotEmpty && site.isNotEmpty) {
          return created
              ? "Passage enregistré: $name sur $site."
              : "Passage déjà enregistré récemment: $name sur $site.";
        }
        return "Passage contrôleur validé.";
      }
      throw Exception(detail ?? "controller_face_checkin_http_${resp.statusCode}");
    } on SocketException {
      throw Exception("network_unreachable");
    } on TimeoutException {
      throw Exception("network_timeout");
    }
  }

  /// Rafraîchit l’access token si un refresh est stocké.
  Future<bool> tryRefreshAccessToken() async {
    final refresh = await getRefreshToken();
    if (refresh == null || refresh.isEmpty) return false;
    final uri = Uri.parse("$apiBase/api/v1/auth/refresh");
    try {
      final resp = await http
          .post(
            uri,
            headers: {"Content-Type": "application/json"},
            body: jsonEncode({"refresh": refresh}),
          )
          .timeout(const Duration(seconds: 20));
      if (resp.statusCode != 200) return false;
      await _storeJwtFromBody(resp.body);
      return true;
    } catch (_) {
      return false;
    }
  }

  Future<void> logout() async {
    await _storage.delete(key: "access_token");
    await _storage.delete(key: "refresh_token");
  }

  Future<List<Assignment>> fetchTodayAssignments() async {
    final token = await getAccessToken();
    final uri = Uri.parse("$apiBase/api/v1/assignments/today");
    final resp = await http.get(
      uri,
      headers: {"Authorization": "Bearer $token"},
    );
    if (resp.statusCode != 200) throw Exception("sync_failed");
    final list = jsonDecode(resp.body) as List<dynamic>;
    return list.map((e) {
      final m = e as Map<String, dynamic>;
      final id = (m["id"] as num).toInt();
      final site = (m["site_name"] ?? "Site ${m["site"]}").toString();
      final start = (m["start_time"] ?? "").toString().substring(0, 5);
      final end = (m["end_time"] ?? "").toString().substring(0, 5);
      final hasStart = (m["has_start"] ?? false) as bool;
      final hasEnd = (m["has_end"] ?? false) as bool;
      final canEnd = (m["can_end"] ?? false) as bool;
      final endBlockReason = (m["end_block_reason"] as String?);
      final presenceDueAtIso =
          (m["presence_due_at"] as String?) ??
          m["presence_due_at_iso"] as String?;
      final shiftRaw = m["shift_date"]?.toString().split("T").first ?? "";
      DateTime shiftDate;
      try {
        shiftDate = DateTime.parse(shiftRaw);
      } catch (_) {
        shiftDate = DateTime.now();
      }
      final d = shiftDate.day.toString().padLeft(2, "0");
      final mo = shiftDate.month.toString().padLeft(2, "0");
      final y = shiftDate.year.toString();

      return Assignment(
        id: id,
        label: "$d/$mo/$y • $site • $start-$end • #$id",
        siteName: site,
        shiftDate: shiftDate,
        startTime: start,
        endTime: end,
        hasStart: hasStart,
        hasEnd: hasEnd,
        canEnd: canEnd,
        endBlockReason: endBlockReason,
        presenceDueAtIso: presenceDueAtIso,
      );
    }).toList();
  }

  Future<String> sendCheckin({
    required String type,
    required int assignmentId,
    required String photoPath,
    required String latitude,
    required String longitude,
    required String verificationToken,
  }) async {
    final token = await getAccessToken();
    final uri = Uri.parse("$apiBase/api/v1/checkins/$type");
    final req = http.MultipartRequest("POST", uri);
    req.headers["Authorization"] = "Bearer $token";
    req.fields["assignment"] = assignmentId.toString();
    req.fields["latitude"] = latitude;
    req.fields["longitude"] = longitude;
    req.fields["verification_token"] = verificationToken;
    req.files.add(
      await http.MultipartFile.fromPath(
        "photo",
        photoPath,
        filename: "selfie.jpg",
      ),
    );
    final streamed = await req.send();
    final resp = await http.Response.fromStream(streamed);
    if (resp.statusCode >= 400) {
      String? serverHint;
      try {
        final decoded = jsonDecode(resp.body);
        if (decoded is Map<String, dynamic>) {
          for (final key in [
            "latitude",
            "longitude",
            "detail",
            "non_field_errors",
          ]) {
            final v = decoded[key];
            if (v is List && v.isNotEmpty) {
              serverHint = v.first.toString();
              break;
            }
            if (v is String && v.isNotEmpty) {
              serverHint = v;
              break;
            }
          }
        }
      } catch (_) {}
      throw Exception(serverHint ?? "refused_${type}_${resp.statusCode}");
    }
    return "Pointage $type valide (${resp.statusCode}).";
  }

  Future<String> requestBiometricChallenge({
    required int assignmentId,
    required String checkinType,
    required String deviceId,
  }) async {
    final token = await getAccessToken();
    final uri = Uri.parse("$apiBase/api/v1/checkins/biometric/challenge");
    final resp = await http.post(
      uri,
      headers: {
        "Authorization": "Bearer $token",
        "Content-Type": "application/json",
      },
      body: jsonEncode({
        "assignment_id": assignmentId,
        "checkin_type": checkinType,
        "device_id": deviceId,
      }),
    );
    if (resp.statusCode != 201) throw Exception("biometric_challenge_failed");
    final data = jsonDecode(resp.body) as Map<String, dynamic>;
    final challengeId = (data["challenge_id"] ?? "").toString();
    if (challengeId.isEmpty) throw Exception("biometric_challenge_invalid");
    return challengeId;
  }

  Future<String> verifyBiometric({
    required String challengeId,
    required String selfiePath,
  }) async {
    final token = await getAccessToken();
    final uri = Uri.parse("$apiBase/api/v1/checkins/biometric/verify");
    final req = http.MultipartRequest("POST", uri);
    req.headers["Authorization"] = "Bearer $token";
    req.fields["challenge_id"] = challengeId;
    req.files.add(
      await http.MultipartFile.fromPath(
        "selfie",
        selfiePath,
        filename: "face_selfie.jpg",
      ),
    );
    final streamed = await req.send();
    final resp = await http.Response.fromStream(streamed);
    if (resp.statusCode != 200) {
      throw Exception("biometric_verify_failed_${resp.statusCode}");
    }
    final data = jsonDecode(resp.body) as Map<String, dynamic>;
    final verificationToken = (data["verification_token"] ?? "").toString();
    if (verificationToken.isEmpty) throw Exception("biometric_verify_invalid");
    return verificationToken;
  }
}
