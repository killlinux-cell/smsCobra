import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_agent/models/assignment.dart';
import 'package:mobile_agent/utils/assignment_pick.dart';

Assignment _a({
  required int id,
  required DateTime shiftDate,
  required String start,
  required String end,
  bool hasStart = false,
  bool hasEnd = false,
  bool canEnd = false,
}) {
  return Assignment(
    id: id,
    label: "#$id",
    siteName: "S",
    shiftDate: shiftDate,
    startTime: start,
    endTime: end,
    hasStart: hasStart,
    hasEnd: hasEnd,
    canEnd: canEnd,
    endBlockReason: null,
    presenceDueAtIso: null,
  );
}

void main() {
  test("n’utilise pas le poste d’hier (même créneau 06–18) le lendemain matin", () {
    final yesterday = DateTime(2026, 4, 3);
    final today = DateTime(2026, 4, 4);
    final now = DateTime(2026, 4, 4, 8, 26);
    final oldShift = _a(
      id: 1,
      shiftDate: yesterday,
      start: "06:00",
      end: "18:00",
      hasStart: true,
      hasEnd: true,
      canEnd: false,
    );
    final todayShift = _a(
      id: 5,
      shiftDate: today,
      start: "06:00",
      end: "18:00",
    );
    final picked = pickActiveAssignment([oldShift, todayShift], now);
    expect(picked?.id, 5);
  });

  test("poste de nuit : partie après minuit utilise shift_date = veille", () {
    final yesterday = DateTime(2026, 4, 3);
    final now = DateTime(2026, 4, 4, 2, 0);
    final night = _a(
      id: 2,
      shiftDate: yesterday,
      start: "18:00",
      end: "06:00",
    );
    expect(assignmentIsActiveNow(night, now), isTrue);
  });

  test("après la fin du jour, retourne le poste du jour civil", () {
    final today = DateTime(2026, 4, 4);
    final now = DateTime(2026, 4, 4, 20, 0);
    final day = _a(
      id: 5,
      shiftDate: today,
      start: "06:00",
      end: "18:00",
      hasStart: true,
      hasEnd: true,
    );
    final picked = pickActiveAssignment([day], now);
    expect(picked?.id, 5);
  });
}
