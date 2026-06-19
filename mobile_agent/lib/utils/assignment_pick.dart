import '../models/assignment.dart';
import 'time_utils.dart';

bool _sameCalendarDate(DateTime a, DateTime b) =>
    a.year == b.year && a.month == b.month && a.day == b.day;

/// Même marge qu'au serveur (`checkins.window.END_GRACE_AFTER_MINUTES`).
const kEndGraceMinutes = 120;

/// True si l'heure locale actuelle tombe dans le créneau [a], en tenant compte
/// de [shiftDate] (indispensable : sans cela, le poste d'hier 06h–18h paraît
/// « actif » le lendemain matin au même horaire).
bool assignmentIsActiveNow(Assignment a, DateTime now) {
  final today = DateTime(now.year, now.month, now.day);
  final yesterday = today.subtract(const Duration(days: 1));
  final nowMin = now.hour * 60 + now.minute;
  final startMin = minutesFromHhMm(a.startTime);
  final endMin = minutesFromHhMm(a.endTime);
  final crossesMidnight = startMin > endMin;
  final endWithGrace = endMin + kEndGraceMinutes;

  if (!crossesMidnight) {
    if (!_sameCalendarDate(a.shiftDate, today)) return false;
    return nowMin >= startMin && nowMin < endWithGrace;
  }
  if (_sameCalendarDate(a.shiftDate, today) && nowMin >= startMin) return true;
  // Matin après minuit : jusqu'à fin + marge (ex. nuit 18h→06h, clôture jusqu'à ~08h).
  if (_sameCalendarDate(a.shiftDate, yesterday) && nowMin < endWithGrace) {
    return true;
  }
  return false;
}

/// Poste à afficher : d'abord celui déjà commencé sans fin (clôture en cours),
/// puis celui actif maintenant, sinon le premier du jour civil local, sinon secours.
Assignment? pickActiveAssignment(List<Assignment> list, DateTime now) {
  if (list.isEmpty) return null;
  for (final a in list) {
    if (a.hasStart && !a.hasEnd) return a;
  }
  for (final a in list) {
    if (assignmentIsActiveNow(a, now)) return a;
  }
  final today = DateTime(now.year, now.month, now.day);
  for (final a in list) {
    if (_sameCalendarDate(a.shiftDate, today)) return a;
  }
  return list.first;
}

/// Choisit le poste affiché après sync API.
/// Ne réapplique pas [preserveAssignmentId] s'il existe déjà un poste commencé
/// sans fin (évite d'écraser la nuit d'hier par l'affectation du jour).
Assignment? resolveSelectedAssignment(
  List<Assignment> list,
  DateTime now, {
  int? preserveAssignmentId,
}) {
  final resolved = pickActiveAssignment(list, now);
  if (preserveAssignmentId == null) return resolved;
  final hasOpenShift = list.any((a) => a.hasStart && !a.hasEnd);
  if (hasOpenShift) return resolved;
  for (final a in list) {
    if (a.id == preserveAssignmentId) return a;
  }
  return resolved;
}
