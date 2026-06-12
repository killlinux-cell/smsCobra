from django.test import TestCase

from accounts.vigile_username_normalize import (
    is_standard_vigile_username,
    plan_vigile_username_normalizations,
    preferred_vigile_username,
)


class VigileUsernameNormalizeTests(TestCase):
    def test_standard_detection(self):
        self.assertTrue(is_standard_vigile_username("VIR-001"))
        self.assertFalse(is_standard_vigile_username("001"))
        self.assertFalse(is_standard_vigile_username("v1"))

    def test_preferred_from_numeric(self):
        self.assertEqual(preferred_vigile_username("001"), "VIR-001")
        self.assertEqual(preferred_vigile_username("7"), "VIR-007")
        self.assertIsNone(preferred_vigile_username("VIR-002"))

    def test_plan_numeric_usernames(self):
        vigiles = [(1, "001"), (2, "002")]
        reserved = {"001", "002", "vir-003"}
        changes, warnings = plan_vigile_username_normalizations(
            vigiles,
            reserved_usernames=reserved,
        )
        self.assertEqual(warnings, [])
        by_id = {c.user_id: c.new_username for c in changes}
        self.assertEqual(by_id[1], "VIR-001")
        self.assertEqual(by_id[2], "VIR-002")

    def test_plan_conflict_with_existing_vir(self):
        vigiles = [(2, "001")]
        reserved = {"001", "vir-001"}
        changes, warnings = plan_vigile_username_normalizations(
            vigiles,
            reserved_usernames=reserved,
        )
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].old_username, "001")
        self.assertEqual(changes[0].new_username, "VIR-002")
        self.assertTrue(warnings)

    def test_plan_numeric_conflict_with_existing_vir_009(self):
        vigiles = [(15, "009")]
        reserved = {"009", "vir-001", "vir-009"}
        changes, warnings = plan_vigile_username_normalizations(
            vigiles,
            reserved_usernames=reserved,
        )
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].new_username, "VIR-002")
        self.assertNotEqual(changes[0].new_username, "VIR-009")
        self.assertTrue(warnings)

    def test_plan_custom_username_gets_next_free(self):
        vigiles = [(5, "custom-id")]
        reserved = {"custom-id", "vir-010"}
        changes, _warnings = plan_vigile_username_normalizations(
            vigiles,
            reserved_usernames=reserved,
        )
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].old_username, "custom-id")
        self.assertEqual(changes[0].new_username, "VIR-011")

    def test_plan_swap_safe_targets(self):
        vigiles = [(1, "001"), (2, "002")]
        reserved = {"001", "002"}
        changes, _warnings = plan_vigile_username_normalizations(
            vigiles,
            reserved_usernames=reserved,
        )
        targets = {c.new_username for c in changes}
        self.assertEqual(targets, {"VIR-001", "VIR-002"})
