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
  test(
    "n’utilise pas le poste d’hier (même créneau 06–18) le lendemain matin",
    () {
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
    },
  );

  test("poste de nuit : partie après minuit utilise shift_date = veille", () {
    final yesterday = DateTime(2026, 4, 3);
    final now = DateTime(2026, 4, 4, 2, 0);
    final night = _a(id: 2, shiftDate: yesterday, start: "18:00", end: "06:00");
    expect(assignmentIsActiveNow(night, now), isTrue);
  });

  test("poste de nuit : encore actif à 06h51 le lendemain (fenêtre de clôture)", () {
    final shiftDay = DateTime(2026, 6, 15);
    final now = DateTime(2026, 6, 16, 6, 51);
    final night = _a(
      id: 4,
      shiftDate: shiftDay,
      start: "18:00",
      end: "06:00",
      hasStart: true,
      hasEnd: false,
      canEnd: true,
    );
    expect(assignmentIsActiveNow(night, now), isTrue);
  });

  test(
    "nuit commencée hier : à 06h51 affiche le poste nuit, pas le poste jour du matin",
    () {
      final shiftDay = DateTime(2026, 6, 15);
      final today = DateTime(2026, 6, 16);
      final now = DateTime(2026, 6, 16, 6, 51);
      final nightOpen = _a(
        id: 4,
        shiftDate: shiftDay,
        start: "18:00",
        end: "06:00",
        hasStart: true,
        hasEnd: false,
        canEnd: true,
      );
      final dayToday = _a(
        id: 9,
        shiftDate: today,
        start: "06:00",
        end: "18:00",
      );
      final picked = pickActiveAssignment([dayToday, nightOpen], now);
      expect(picked?.id, 4);
      expect(picked?.hasStart, isTrue);
      expect(picked?.hasEnd, isFalse);
    },
  );

  test(
    "ne réapplique pas preserveId si un poste nuit est encore ouvert (pointé hier)",
    () {
      final shiftDay = DateTime(2026, 6, 18);
      final today = DateTime(2026, 6, 19);
      final now = DateTime(2026, 6, 19, 8, 26);
      final nightOpen = _a(
        id: 2200,
        shiftDate: shiftDay,
        start: "18:30",
        end: "06:30",
        hasStart: true,
        hasEnd: false,
        canEnd: true,
      );
      final todayNight = _a(
        id: 2263,
        shiftDate: today,
        start: "18:30",
        end: "06:30",
      );
      final picked = resolveSelectedAssignment(
        [todayNight, nightOpen],
        now,
        preserveAssignmentId: 2263,
      );
      expect(picked?.id, 2200);
    },
  );

  test(
    "poste jour d'hier ouvert sans fin : le lendemain matin sélectionne le poste du jour",
    () {
      final yesterday = DateTime(2026, 7, 10);
      final today = DateTime(2026, 7, 11);
      final now = DateTime(2026, 7, 11, 7, 0);
      final staleOpen = _a(
        id: 1,
        shiftDate: yesterday,
        start: "06:30",
        end: "18:30",
        hasStart: true,
        hasEnd: false,
      );
      final todayShift = _a(
        id: 2,
        shiftDate: today,
        start: "06:30",
        end: "18:30",
      );
      final picked = pickActiveAssignment([staleOpen, todayShift], now);
      expect(picked?.id, 2);
    },
  );

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
