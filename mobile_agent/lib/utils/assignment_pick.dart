import '../models/assignment.dart';
import 'time_utils.dart';

bool _sameCalendarDate(DateTime a, DateTime b) =>
    a.year == b.year && a.month == b.month && a.day == b.day;

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

  if (!crossesMidnight) {
    if (!_sameCalendarDate(a.shiftDate, today)) return false;
    return nowMin >= startMin && nowMin < endMin;
  }
  if (_sameCalendarDate(a.shiftDate, today) && nowMin >= startMin) return true;
  if (_sameCalendarDate(a.shiftDate, yesterday) && nowMin < endMin) return true;
  return false;
}

/// Poste à afficher : d'abord celui actif maintenant, sinon le premier du jour
/// civil local, sinon la première ligne (comportement de secours).
Assignment? pickActiveAssignment(List<Assignment> list, DateTime now) {
  if (list.isEmpty) return null;
  for (final a in list) {
    if (assignmentIsActiveNow(a, now)) return a;
  }
  final today = DateTime(now.year, now.month, now.day);
  for (final a in list) {
    if (_sameCalendarDate(a.shiftDate, today)) return a;
  }
  return list.first;
}
