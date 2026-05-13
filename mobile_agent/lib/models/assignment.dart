class Assignment {
  Assignment({
    required this.id,
    required this.label,
    required this.siteName,
    required this.shiftDate,
    required this.startTime,
    required this.endTime,
    required this.hasStart,
    required this.hasEnd,
    required this.canEnd,
    required this.endBlockReason,
    required this.presenceDueAtIso,
  });

  final int id;
  final String label;
  final String siteName;
  /// Date du poste (jour de la planification), fuseau / calendrier local côté app.
  final DateTime shiftDate;
  final String startTime; // HH:mm
  final String endTime; // HH:mm
  final bool hasStart;
  final bool hasEnd;
  final bool canEnd;
  final String? endBlockReason;
  final String? presenceDueAtIso;
}

