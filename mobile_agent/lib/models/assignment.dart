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

  Assignment copyWith({
    int? id,
    String? label,
    String? siteName,
    DateTime? shiftDate,
    String? startTime,
    String? endTime,
    bool? hasStart,
    bool? hasEnd,
    bool? canEnd,
    String? endBlockReason,
    String? presenceDueAtIso,
    bool clearEndBlockReason = false,
  }) {
    return Assignment(
      id: id ?? this.id,
      label: label ?? this.label,
      siteName: siteName ?? this.siteName,
      shiftDate: shiftDate ?? this.shiftDate,
      startTime: startTime ?? this.startTime,
      endTime: endTime ?? this.endTime,
      hasStart: hasStart ?? this.hasStart,
      hasEnd: hasEnd ?? this.hasEnd,
      canEnd: canEnd ?? this.canEnd,
      endBlockReason:
          clearEndBlockReason ? null : (endBlockReason ?? this.endBlockReason),
      presenceDueAtIso: presenceDueAtIso ?? this.presenceDueAtIso,
    );
  }
}

