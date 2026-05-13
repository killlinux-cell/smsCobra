int minutesFromHhMm(String hhMm) {
  final parts = hhMm.split(":");
  if (parts.length != 2) return 0;
  final h = int.tryParse(parts[0]) ?? 0;
  final m = int.tryParse(parts[1]) ?? 0;
  return h * 60 + m;
}

DateTime? parseIsoOrNull(String? iso) {
  if (iso == null || iso.isEmpty) return null;
  try {
    return DateTime.parse(iso);
  } catch (_) {
    return null;
  }
}

