class AdminProfile {
  const AdminProfile({
    required this.id,
    required this.username,
    required this.firstName,
    required this.lastName,
    required this.role,
    this.phoneNumber,
    this.profilePhotoPath,
  });

  final int id;
  final String username;
  final String firstName;
  final String lastName;
  final String role;
  final String? phoneNumber;
  final String? profilePhotoPath;

  String get displayName {
    final n = "$firstName $lastName".trim();
    return n.isEmpty ? username : n;
  }

  String get matricule => username;

  String get initials {
    if (firstName.isNotEmpty && lastName.isNotEmpty) {
      return "${firstName[0]}${lastName[0]}".toUpperCase();
    }
    if (firstName.isNotEmpty) return firstName[0].toUpperCase();
    if (username.length >= 2) return username.substring(0, 2).toUpperCase();
    return "?";
  }

  /// Libellé français pour l’UI.
  String get roleLabel {
    switch (role) {
      case "super_admin":
        return "Super administrateur";
      case "admin_societe":
        return "Administrateur société";
      case "superviseur":
        return "Superviseur";
      default:
        return role;
    }
  }

  static AdminProfile? fromJson(Map<String, dynamic>? m) {
    if (m == null) return null;
    return AdminProfile(
      id: (m["id"] as num?)?.toInt() ?? 0,
      username: (m["username"] ?? "").toString(),
      firstName: (m["first_name"] ?? "").toString(),
      lastName: (m["last_name"] ?? "").toString(),
      role: (m["role"] ?? "").toString(),
      phoneNumber: m["phone_number"]?.toString(),
      profilePhotoPath: m["profile_photo"]?.toString(),
    );
  }
}
