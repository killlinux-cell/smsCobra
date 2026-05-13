class AgentProfile {
  const AgentProfile({
    required this.id,
    required this.username,
    required this.firstName,
    required this.lastName,
    this.profilePhotoPath,
  });

  final int id;
  final String username;
  final String firstName;
  final String lastName;
  /// Chemin relatif ou URL absolue renvoyé par l’API (ex. /media/profiles/…).
  final String? profilePhotoPath;

  String get displayName {
    final n = "$firstName $lastName".trim();
    return n.isEmpty ? username : n;
  }

  /// Matricule = identifiant de connexion (ex. VIR-001).
  String get matricule => username;

  String get initials {
    if (firstName.isNotEmpty && lastName.isNotEmpty) {
      return "${firstName[0]}${lastName[0]}".toUpperCase();
    }
    if (firstName.isNotEmpty) return firstName[0].toUpperCase();
    if (username.length >= 2) return username.substring(0, 2).toUpperCase();
    return "?";
  }

  static AgentProfile? fromJson(Map<String, dynamic>? m) {
    if (m == null) return null;
    return AgentProfile(
      id: (m["id"] as num?)?.toInt() ?? 0,
      username: (m["username"] ?? "").toString(),
      firstName: (m["first_name"] ?? "").toString(),
      lastName: (m["last_name"] ?? "").toString(),
      profilePhotoPath: m["profile_photo"]?.toString(),
    );
  }
}
