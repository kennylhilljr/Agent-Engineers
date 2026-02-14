"""Comprehensive tests for XP and level calculation functions.

Tests cover:
- XP awards for all action types
- Level thresholds and boundary cases
- Streak calculations
- Edge cases (zero XP, max level, etc.)
- All pure functions are deterministic and side-effect free
"""

import unittest
from xp_calculations import (
    calculate_xp_for_successful_invocation,
    calculate_xp_for_contribution_type,
    calculate_speed_bonus,
    calculate_error_recovery_bonus,
    calculate_streak_bonus,
    calculate_total_xp_for_success,
    get_level_thresholds,
    get_level_title,
    calculate_level_from_xp,
    calculate_xp_for_next_level,
    calculate_xp_progress_in_level,
    update_streak,
)


class TestXPAwards(unittest.TestCase):
    """Test suite for XP award calculations."""

    def test_successful_invocation_base_xp(self):
        """Test base XP for successful invocation."""
        xp = calculate_xp_for_successful_invocation()
        self.assertEqual(xp, 10)

    def test_successful_invocation_custom_xp(self):
        """Test base XP with custom amount."""
        xp = calculate_xp_for_successful_invocation(base_xp=15)
        self.assertEqual(xp, 15)

    def test_successful_invocation_zero_xp(self):
        """Test base XP with zero amount."""
        xp = calculate_xp_for_successful_invocation(base_xp=0)
        self.assertEqual(xp, 0)

    def test_successful_invocation_high_xp(self):
        """Test base XP with high amount."""
        xp = calculate_xp_for_successful_invocation(base_xp=100)
        self.assertEqual(xp, 100)


class TestContributionTypes(unittest.TestCase):
    """Test suite for contribution type XP calculations."""

    def test_contribution_commit(self):
        """Test XP for commit."""
        xp = calculate_xp_for_contribution_type("commit")
        self.assertEqual(xp, 5)

    def test_contribution_pr_created(self):
        """Test XP for PR created."""
        xp = calculate_xp_for_contribution_type("pr_created")
        self.assertEqual(xp, 15)

    def test_contribution_pr_merged(self):
        """Test XP for PR merged."""
        xp = calculate_xp_for_contribution_type("pr_merged")
        self.assertEqual(xp, 30)

    def test_contribution_test_written(self):
        """Test XP for test written."""
        xp = calculate_xp_for_contribution_type("test_written")
        self.assertEqual(xp, 20)

    def test_contribution_ticket_completed(self):
        """Test XP for ticket completed."""
        xp = calculate_xp_for_contribution_type("ticket_completed")
        self.assertEqual(xp, 25)

    def test_contribution_file_created(self):
        """Test XP for file created."""
        xp = calculate_xp_for_contribution_type("file_created")
        self.assertEqual(xp, 3)

    def test_contribution_file_modified(self):
        """Test XP for file modified."""
        xp = calculate_xp_for_contribution_type("file_modified")
        self.assertEqual(xp, 2)

    def test_contribution_issue_created(self):
        """Test XP for issue created."""
        xp = calculate_xp_for_contribution_type("issue_created")
        self.assertEqual(xp, 8)

    def test_contribution_unknown_type(self):
        """Test that unknown contribution type raises error."""
        with self.assertRaises(ValueError) as context:
            calculate_xp_for_contribution_type("unknown_contribution")
        self.assertIn("Unknown contribution type", str(context.exception))

    def test_contribution_all_types_positive(self):
        """Test that all contribution types return positive XP."""
        contribution_types = [
            "commit", "pr_created", "pr_merged", "test_written",
            "ticket_completed", "file_created", "file_modified", "issue_created"
        ]
        for ctype in contribution_types:
            xp = calculate_xp_for_contribution_type(ctype)
            self.assertGreater(xp, 0, f"Contribution type {ctype} should have positive XP")


class TestSpeedBonus(unittest.TestCase):
    """Test suite for speed bonus calculations."""

    def test_speed_bonus_very_fast(self):
        """Test bonus for very fast completion (< 30s)."""
        bonus = calculate_speed_bonus(15.5)
        self.assertEqual(bonus, 10)

    def test_speed_bonus_fast_edge_case_29_seconds(self):
        """Test bonus at 29 second boundary."""
        bonus = calculate_speed_bonus(29.0)
        self.assertEqual(bonus, 10)

    def test_speed_bonus_fast_edge_case_30_seconds(self):
        """Test bonus at 30 second boundary."""
        bonus = calculate_speed_bonus(30.0)
        self.assertEqual(bonus, 5)

    def test_speed_bonus_moderate(self):
        """Test bonus for moderate speed (30-60s)."""
        bonus = calculate_speed_bonus(45.0)
        self.assertEqual(bonus, 5)

    def test_speed_bonus_moderate_edge_case_59_seconds(self):
        """Test bonus at 59 second boundary."""
        bonus = calculate_speed_bonus(59.0)
        self.assertEqual(bonus, 5)

    def test_speed_bonus_moderate_edge_case_60_seconds(self):
        """Test bonus at 60 second boundary."""
        bonus = calculate_speed_bonus(60.0)
        self.assertEqual(bonus, 0)

    def test_speed_bonus_slow(self):
        """Test no bonus for slow completion (>= 60s)."""
        bonus = calculate_speed_bonus(120.0)
        self.assertEqual(bonus, 0)

    def test_speed_bonus_very_slow(self):
        """Test no bonus for very slow completion."""
        bonus = calculate_speed_bonus(300.0)
        self.assertEqual(bonus, 0)

    def test_speed_bonus_instant(self):
        """Test bonus for near-instant completion."""
        bonus = calculate_speed_bonus(0.1)
        self.assertEqual(bonus, 10)

    def test_speed_bonus_boundary_just_under_30(self):
        """Test boundary just under 30 seconds."""
        bonus = calculate_speed_bonus(29.99)
        self.assertEqual(bonus, 10)

    def test_speed_bonus_boundary_just_under_60(self):
        """Test boundary just under 60 seconds."""
        bonus = calculate_speed_bonus(59.99)
        self.assertEqual(bonus, 5)


class TestErrorRecoveryBonus(unittest.TestCase):
    """Test suite for error recovery bonus."""

    def test_error_recovery_after_error(self):
        """Test recovery bonus after error status."""
        bonus = calculate_error_recovery_bonus(1, "error")
        self.assertEqual(bonus, 10)

    def test_error_recovery_after_timeout(self):
        """Test recovery bonus after timeout status."""
        bonus = calculate_error_recovery_bonus(1, "timeout")
        self.assertEqual(bonus, 10)

    def test_error_recovery_after_blocked(self):
        """Test recovery bonus after blocked status."""
        bonus = calculate_error_recovery_bonus(1, "blocked")
        self.assertEqual(bonus, 10)

    def test_no_recovery_bonus_after_success(self):
        """Test no bonus when previous status was success."""
        bonus = calculate_error_recovery_bonus(2, "success")
        self.assertEqual(bonus, 0)

    def test_no_recovery_bonus_when_not_immediate(self):
        """Test no bonus if streak is longer than 1."""
        bonus = calculate_error_recovery_bonus(2, "error")
        self.assertEqual(bonus, 0)

    def test_no_recovery_bonus_zero_streak(self):
        """Test no bonus with zero streak."""
        bonus = calculate_error_recovery_bonus(0, "error")
        self.assertEqual(bonus, 0)

    def test_recovery_bonus_all_failure_types(self):
        """Test recovery bonus for all failure status types."""
        failure_statuses = ["error", "timeout", "blocked"]
        for status in failure_statuses:
            bonus = calculate_error_recovery_bonus(1, status)
            self.assertEqual(bonus, 10, f"Recovery bonus should apply for status: {status}")


class TestStreakBonus(unittest.TestCase):
    """Test suite for streak bonus calculations."""

    def test_streak_bonus_single_success(self):
        """Test streak bonus for single success."""
        bonus = calculate_streak_bonus(1)
        self.assertEqual(bonus, 1)

    def test_streak_bonus_five_successes(self):
        """Test streak bonus for 5 successes."""
        bonus = calculate_streak_bonus(5)
        self.assertEqual(bonus, 5)

    def test_streak_bonus_ten_successes(self):
        """Test streak bonus for 10 successes."""
        bonus = calculate_streak_bonus(10)
        self.assertEqual(bonus, 10)

    def test_streak_bonus_high_streak(self):
        """Test streak bonus for long streak."""
        bonus = calculate_streak_bonus(25)
        self.assertEqual(bonus, 25)

    def test_streak_bonus_zero(self):
        """Test streak bonus for zero streak."""
        bonus = calculate_streak_bonus(0)
        self.assertEqual(bonus, 0)

    def test_streak_bonus_negative(self):
        """Test streak bonus handles negative values gracefully."""
        bonus = calculate_streak_bonus(-5)
        self.assertEqual(bonus, 0)


class TestTotalXPCalculation(unittest.TestCase):
    """Test suite for total XP calculation."""

    def test_total_xp_default_values(self):
        """Test total XP with default parameters."""
        xp = calculate_total_xp_for_success()
        # 10 base + 0 speed + 0 recovery + 0 contribution + 1 streak = 11
        self.assertEqual(xp, 11)

    def test_total_xp_with_speed_bonus(self):
        """Test total XP including speed bonus."""
        xp = calculate_total_xp_for_success(duration_seconds=25.0)
        # 10 base + 10 speed + 0 recovery + 0 contribution + 1 streak = 21
        self.assertEqual(xp, 21)

    def test_total_xp_with_error_recovery(self):
        """Test total XP including error recovery bonus."""
        xp = calculate_total_xp_for_success(current_streak=1, previous_status="error")
        # 10 base + 0 speed + 10 recovery + 0 contribution + 1 streak = 21
        self.assertEqual(xp, 21)

    def test_total_xp_with_contribution(self):
        """Test total XP including contribution bonus."""
        xp = calculate_total_xp_for_success(contribution_xp=25)
        # 10 base + 0 speed + 0 recovery + 25 contribution + 1 streak = 36
        self.assertEqual(xp, 36)

    def test_total_xp_with_long_streak(self):
        """Test total XP with longer streak."""
        xp = calculate_total_xp_for_success(current_streak=5)
        # 10 base + 0 speed + 0 recovery + 0 contribution + 5 streak = 15
        self.assertEqual(xp, 15)

    def test_total_xp_all_bonuses(self):
        """Test total XP with all bonuses."""
        xp = calculate_total_xp_for_success(
            base_xp=10,
            duration_seconds=25.0,
            current_streak=1,
            previous_status="error",
            contribution_xp=30
        )
        # 10 base + 10 speed + 10 recovery + 30 contribution + 1 streak = 61
        self.assertEqual(xp, 61)

    def test_total_xp_zero_all(self):
        """Test total XP with zero contributions."""
        xp = calculate_total_xp_for_success(
            base_xp=0,
            duration_seconds=120.0,
            current_streak=0,
            previous_status="success",
            contribution_xp=0
        )
        self.assertEqual(xp, 0)

    def test_total_xp_high_contribution(self):
        """Test total XP with high contribution value."""
        xp = calculate_total_xp_for_success(contribution_xp=100)
        # 10 base + 0 speed + 0 recovery + 100 contribution + 1 streak = 111
        self.assertEqual(xp, 111)


class TestLevelThresholds(unittest.TestCase):
    """Test suite for level threshold calculations."""

    def test_level_thresholds_count(self):
        """Test that there are 8 levels."""
        thresholds = get_level_thresholds()
        self.assertEqual(len(thresholds), 8)

    def test_level_thresholds_values(self):
        """Test that threshold values are correct."""
        expected = [0, 50, 150, 400, 800, 1500, 3000, 5000]
        thresholds = get_level_thresholds()
        self.assertEqual(thresholds, expected)

    def test_level_thresholds_ascending(self):
        """Test that thresholds are in ascending order."""
        thresholds = get_level_thresholds()
        for i in range(len(thresholds) - 1):
            self.assertLess(thresholds[i], thresholds[i + 1])

    def test_level_thresholds_start_at_zero(self):
        """Test that first threshold is 0."""
        thresholds = get_level_thresholds()
        self.assertEqual(thresholds[0], 0)

    def test_level_thresholds_exponential_growth(self):
        """Test that thresholds grow exponentially."""
        thresholds = get_level_thresholds()
        # Check that growth is roughly exponential
        # Each gap should be larger than the previous
        gaps = [thresholds[i+1] - thresholds[i] for i in range(len(thresholds)-1)]
        for i in range(len(gaps) - 1):
            self.assertGreater(gaps[i+1], gaps[i] * 0.5)  # Allowing some flexibility


class TestLevelTitles(unittest.TestCase):
    """Test suite for level title retrieval."""

    def test_level_1_title(self):
        """Test title for level 1."""
        title = get_level_title(1)
        self.assertEqual(title, "Intern")

    def test_level_2_title(self):
        """Test title for level 2."""
        title = get_level_title(2)
        self.assertEqual(title, "Junior")

    def test_level_3_title(self):
        """Test title for level 3."""
        title = get_level_title(3)
        self.assertEqual(title, "Mid-Level")

    def test_level_4_title(self):
        """Test title for level 4."""
        title = get_level_title(4)
        self.assertEqual(title, "Senior")

    def test_level_5_title(self):
        """Test title for level 5."""
        title = get_level_title(5)
        self.assertEqual(title, "Staff")

    def test_level_6_title(self):
        """Test title for level 6."""
        title = get_level_title(6)
        self.assertEqual(title, "Principal")

    def test_level_7_title(self):
        """Test title for level 7."""
        title = get_level_title(7)
        self.assertEqual(title, "Distinguished")

    def test_level_8_title(self):
        """Test title for level 8."""
        title = get_level_title(8)
        self.assertEqual(title, "Fellow")

    def test_level_title_invalid_low(self):
        """Test that invalid low level raises error."""
        with self.assertRaises(ValueError):
            get_level_title(0)

    def test_level_title_invalid_high(self):
        """Test that invalid high level raises error."""
        with self.assertRaises(ValueError):
            get_level_title(9)

    def test_level_title_invalid_negative(self):
        """Test that negative level raises error."""
        with self.assertRaises(ValueError):
            get_level_title(-1)


class TestLevelCalculation(unittest.TestCase):
    """Test suite for calculating level from XP."""

    def test_level_at_zero_xp(self):
        """Test level 1 at 0 XP."""
        level = calculate_level_from_xp(0)
        self.assertEqual(level, 1)

    def test_level_at_threshold_boundaries(self):
        """Test levels at each threshold boundary."""
        test_cases = [
            (0, 1),      # At threshold for level 1
            (49, 1),     # Just before level 2
            (50, 2),     # At threshold for level 2
            (149, 2),    # Just before level 3
            (150, 3),    # At threshold for level 3
            (399, 3),    # Just before level 4
            (400, 4),    # At threshold for level 4
            (799, 4),    # Just before level 5
            (800, 5),    # At threshold for level 5
            (1499, 5),   # Just before level 6
            (1500, 6),   # At threshold for level 6
            (2999, 6),   # Just before level 7
            (3000, 7),   # At threshold for level 7
            (4999, 7),   # Just before level 8
            (5000, 8),   # At threshold for level 8
        ]
        for xp, expected_level in test_cases:
            level = calculate_level_from_xp(xp)
            self.assertEqual(level, expected_level, f"XP {xp} should be level {expected_level}, got {level}")

    def test_level_above_max(self):
        """Test that XP above max level stays at level 8."""
        level = calculate_level_from_xp(10000)
        self.assertEqual(level, 8)

    def test_level_far_above_max(self):
        """Test that very high XP stays at level 8."""
        level = calculate_level_from_xp(1000000)
        self.assertEqual(level, 8)

    def test_level_between_thresholds(self):
        """Test levels between thresholds."""
        # Test in level 1 range
        self.assertEqual(calculate_level_from_xp(25), 1)
        # Test in level 2 range
        self.assertEqual(calculate_level_from_xp(75), 2)
        # Test in level 3 range
        self.assertEqual(calculate_level_from_xp(200), 3)
        # Test in level 4 range
        self.assertEqual(calculate_level_from_xp(600), 4)


class TestXPForNextLevel(unittest.TestCase):
    """Test suite for XP needed for next level."""

    def test_xp_next_level_from_start(self):
        """Test XP needed for first level up."""
        xp_needed = calculate_xp_for_next_level(0)
        self.assertEqual(xp_needed, 50)

    def test_xp_next_level_partway_through(self):
        """Test XP needed partway through a level."""
        xp_needed = calculate_xp_for_next_level(25)
        self.assertEqual(xp_needed, 25)

    def test_xp_next_level_almost_complete(self):
        """Test XP needed when almost at next level."""
        xp_needed = calculate_xp_for_next_level(49)
        self.assertEqual(xp_needed, 1)

    def test_xp_next_level_at_threshold(self):
        """Test XP needed at level threshold."""
        xp_needed = calculate_xp_for_next_level(50)
        self.assertEqual(xp_needed, 100)

    def test_xp_next_level_mid_range(self):
        """Test XP needed in middle of progression."""
        xp_needed = calculate_xp_for_next_level(400)
        self.assertEqual(xp_needed, 400)

    def test_xp_next_level_at_max(self):
        """Test XP needed at max level."""
        xp_needed = calculate_xp_for_next_level(5000)
        self.assertEqual(xp_needed, 0)

    def test_xp_next_level_above_max(self):
        """Test XP needed above max level."""
        xp_needed = calculate_xp_for_next_level(10000)
        self.assertEqual(xp_needed, 0)


class TestXPProgress(unittest.TestCase):
    """Test suite for XP progress within level."""

    def test_progress_at_start_of_level(self):
        """Test progress at start of level."""
        current, total = calculate_xp_progress_in_level(0)
        self.assertEqual(current, 0)
        self.assertEqual(total, 50)

    def test_progress_partway_through_level(self):
        """Test progress partway through level."""
        current, total = calculate_xp_progress_in_level(25)
        self.assertEqual(current, 25)
        self.assertEqual(total, 50)

    def test_progress_at_end_of_level(self):
        """Test progress at threshold of next level."""
        current, total = calculate_xp_progress_in_level(50)
        self.assertEqual(current, 0)
        self.assertEqual(total, 100)

    def test_progress_in_level_2(self):
        """Test progress in level 2."""
        current, total = calculate_xp_progress_in_level(75)
        self.assertEqual(current, 25)
        self.assertEqual(total, 100)

    def test_progress_in_level_3(self):
        """Test progress in level 3."""
        current, total = calculate_xp_progress_in_level(250)
        self.assertEqual(current, 100)
        self.assertEqual(total, 250)

    def test_progress_at_max_level(self):
        """Test progress at max level."""
        current, total = calculate_xp_progress_in_level(5000)
        self.assertEqual(current, 0)
        self.assertEqual(total, 0)

    def test_progress_above_max_level(self):
        """Test progress above max level."""
        current, total = calculate_xp_progress_in_level(10000)
        self.assertEqual(current, 0)
        self.assertEqual(total, 0)


class TestStreakUpdates(unittest.TestCase):
    """Test suite for streak update logic."""

    def test_streak_first_success(self):
        """Test streak update on first success."""
        streak, best = update_streak(0, "success", "success", 0)
        self.assertEqual(streak, 1)
        self.assertEqual(best, 1)

    def test_streak_continuing_success(self):
        """Test streak update on continuing success."""
        streak, best = update_streak(1, "success", "success", 1)
        self.assertEqual(streak, 2)
        self.assertEqual(best, 2)

    def test_streak_long_continuing_success(self):
        """Test streak update with long streak."""
        streak, best = update_streak(5, "success", "success", 5)
        self.assertEqual(streak, 6)
        self.assertEqual(best, 6)

    def test_streak_recovery_from_error(self):
        """Test streak recovery after error."""
        streak, best = update_streak(2, "success", "success", 2)
        self.assertEqual(streak, 3)
        self.assertEqual(best, 3)

    def test_streak_reset_on_error(self):
        """Test streak reset on error."""
        streak, best = update_streak(2, "success", "error", 2)
        self.assertEqual(streak, 0)
        self.assertEqual(best, 2)

    def test_streak_reset_on_timeout(self):
        """Test streak reset on timeout."""
        streak, best = update_streak(5, "success", "timeout", 5)
        self.assertEqual(streak, 0)
        self.assertEqual(best, 5)

    def test_streak_reset_on_blocked(self):
        """Test streak reset on blocked."""
        streak, best = update_streak(3, "success", "blocked", 3)
        self.assertEqual(streak, 0)
        self.assertEqual(best, 3)

    def test_streak_best_updated(self):
        """Test that best streak is updated."""
        streak, best = update_streak(4, "success", "success", 4)
        self.assertEqual(best, 5)

    def test_streak_best_not_downgraded(self):
        """Test that best streak is not downgraded."""
        streak, best = update_streak(2, "success", "error", 10)
        self.assertEqual(streak, 0)
        self.assertEqual(best, 10)

    def test_streak_all_failure_types(self):
        """Test streak reset for all failure types."""
        failure_statuses = ["error", "timeout", "blocked"]
        for status in failure_statuses:
            streak, best = update_streak(3, "success", status, 3)
            self.assertEqual(streak, 0, f"Streak should reset on {status}")
            self.assertEqual(best, 3, f"Best should not change on {status}")


class TestEdgeCases(unittest.TestCase):
    """Test suite for edge cases and boundary conditions."""

    def test_zero_xp_zero_level(self):
        """Test that zero XP gives level 1, not 0."""
        level = calculate_level_from_xp(0)
        self.assertGreaterEqual(level, 1)

    def test_negative_xp_handling(self):
        """Test handling of negative XP."""
        # Should still return level 1
        level = calculate_level_from_xp(-100)
        self.assertEqual(level, 1)

    def test_max_level_cap(self):
        """Test that level is capped at 8."""
        for xp in [5000, 10000, 100000, 1000000]:
            level = calculate_level_from_xp(xp)
            self.assertEqual(level, 8)

    def test_contribution_xp_additive(self):
        """Test that contribution XP adds properly."""
        xp1 = calculate_total_xp_for_success(contribution_xp=0)
        xp2 = calculate_total_xp_for_success(contribution_xp=25)
        self.assertEqual(xp2 - xp1, 25)

    def test_speed_bonus_not_cumulative(self):
        """Test that speed bonus is either/or, not both."""
        xp_fast = calculate_speed_bonus(15.0)
        xp_moderate = calculate_speed_bonus(45.0)
        # Should be different bonuses
        self.assertNotEqual(xp_fast, xp_moderate)
        self.assertEqual(xp_fast, 10)
        self.assertEqual(xp_moderate, 5)

    def test_streak_never_negative(self):
        """Test that streak calculation never goes negative."""
        streak, best = update_streak(0, "success", "error", 5)
        self.assertGreaterEqual(streak, 0)
        self.assertGreaterEqual(best, 0)

    def test_threshold_consistency(self):
        """Test consistency of threshold function."""
        thresholds = get_level_thresholds()
        # Should always return same value
        thresholds2 = get_level_thresholds()
        self.assertEqual(thresholds, thresholds2)

    def test_level_title_all_valid(self):
        """Test that all valid levels have titles."""
        for level in range(1, 9):
            title = get_level_title(level)
            self.assertIsInstance(title, str)
            self.assertGreater(len(title), 0)


class TestIntegrationScenarios(unittest.TestCase):
    """Integration tests for realistic scenarios."""

    def test_scenario_new_agent_first_success(self):
        """Test XP and level for new agent's first success."""
        xp = calculate_total_xp_for_success(current_streak=1)
        level = calculate_level_from_xp(xp)
        self.assertEqual(xp, 11)  # 10 base + 1 streak
        self.assertEqual(level, 1)

    def test_scenario_fast_error_recovery(self):
        """Test XP for fast error recovery."""
        xp = calculate_total_xp_for_success(
            duration_seconds=20.0,
            current_streak=1,
            previous_status="error",
            contribution_xp=0
        )
        # 10 base + 10 speed + 10 recovery + 0 contribution + 1 streak = 31
        self.assertEqual(xp, 31)

    def test_scenario_merged_pr_contribution(self):
        """Test XP for merged PR."""
        pr_xp = calculate_xp_for_contribution_type("pr_merged")
        total_xp = calculate_total_xp_for_success(contribution_xp=pr_xp)
        # 10 base + 0 speed + 0 recovery + 30 contribution + 1 streak = 41
        self.assertEqual(total_xp, 41)

    def test_scenario_leveling_progression(self):
        """Test progression through multiple levels."""
        xp_amounts = [0, 50, 150, 400, 800, 1500, 3000, 5000]
        expected_levels = [1, 2, 3, 4, 5, 6, 7, 8]

        for xp, expected_level in zip(xp_amounts, expected_levels):
            level = calculate_level_from_xp(xp)
            self.assertEqual(level, expected_level)

    def test_scenario_streak_recovery_sequence(self):
        """Test a sequence of streak ups and downs."""
        streak = 0
        best = 0

        # Three successes
        for _ in range(3):
            streak, best = update_streak(streak, "success", "success", best)
        self.assertEqual(streak, 3)
        self.assertEqual(best, 3)

        # One failure
        streak, best = update_streak(streak, "success", "error", best)
        self.assertEqual(streak, 0)
        self.assertEqual(best, 3)

        # Four more successes
        for _ in range(4):
            streak, best = update_streak(streak, "success", "success", best)
        self.assertEqual(streak, 4)
        self.assertEqual(best, 4)


if __name__ == "__main__":
    unittest.main()
