"""XP and level calculation functions for agent gamification.

This module provides pure functions for calculating experience points (XP) and
level progression. All functions are deterministic with no side effects, making
them easy to test and reason about.

XP Awards:
- Successful delegation: +10 base XP
- Different contribution types: commits (+5), PRs created (+15), PRs merged (+30),
  tests written (+20), tickets completed (+25)
- Speed bonus: +5 for completions under 60 seconds
- Error recovery: +10 for success after previous failure
- Streak bonus: +1 XP per consecutive success

Level Progression:
- Exponential-style thresholds using Fibonacci-like sequence
- 8 levels total (Intern through Fellow)
- Thresholds: 0, 50, 150, 400, 800, 1500, 3000, 5000 XP
"""


def calculate_xp_for_successful_invocation(base_xp: int = 10) -> int:
    """Calculate XP for a successful agent invocation.

    Args:
        base_xp: Base XP to award for success (default 10)

    Returns:
        XP amount for successful invocation

    Examples:
        >>> calculate_xp_for_successful_invocation()
        10
        >>> calculate_xp_for_successful_invocation(base_xp=15)
        15
    """
    return base_xp


def calculate_xp_for_contribution_type(contribution_type: str) -> int:
    """Calculate XP based on contribution type.

    Different agent actions are worth different XP amounts based on their
    complexity and impact:
    - commit: +5 XP (Git operations)
    - pr_created: +15 XP (GitHub pull request creation)
    - pr_merged: +30 XP (GitHub pull request merge)
    - test_written: +20 XP (Testing)
    - ticket_completed: +25 XP (Linear issue closure)
    - file_created: +3 XP (File creation)
    - file_modified: +2 XP (File modification)
    - issue_created: +8 XP (Linear issue creation)

    Args:
        contribution_type: Type of contribution (e.g., "commit", "pr_merged")

    Returns:
        XP amount for the contribution type

    Raises:
        ValueError: If contribution_type is unknown

    Examples:
        >>> calculate_xp_for_contribution_type("commit")
        5
        >>> calculate_xp_for_contribution_type("pr_merged")
        30
        >>> calculate_xp_for_contribution_type("unknown")
        Traceback (most recent call last):
            ...
        ValueError: Unknown contribution type: unknown
    """
    contributions = {
        "commit": 5,
        "pr_created": 15,
        "pr_merged": 30,
        "test_written": 20,
        "ticket_completed": 25,
        "file_created": 3,
        "file_modified": 2,
        "issue_created": 8,
    }

    if contribution_type not in contributions:
        raise ValueError(f"Unknown contribution type: {contribution_type}")

    return contributions[contribution_type]


def calculate_speed_bonus(duration_seconds: float) -> int:
    """Calculate speed bonus for quick completions.

    Rewards agents that complete tasks quickly:
    - Under 30 seconds: +10 XP
    - Under 60 seconds: +5 XP
    - 60+ seconds: 0 XP

    Args:
        duration_seconds: Duration of invocation in seconds

    Returns:
        XP bonus for speed (0, 5, or 10)

    Examples:
        >>> calculate_speed_bonus(15.5)
        10
        >>> calculate_speed_bonus(45.0)
        5
        >>> calculate_speed_bonus(120.0)
        0
    """
    if duration_seconds < 30:
        return 10
    elif duration_seconds < 60:
        return 5
    else:
        return 0


def calculate_error_recovery_bonus(consecutive_successes: int,
                                    previous_status: str) -> int:
    """Calculate bonus for recovering from previous errors.

    Rewards agents that succeed after failure:
    - Success immediately after error: +10 XP
    - Success after no previous failures: 0 XP

    Args:
        consecutive_successes: Current streak length (after success)
        previous_status: Status of the previous invocation
                        ("success", "error", "timeout", "blocked")

    Returns:
        XP bonus for error recovery (0 or 10)

    Examples:
        >>> calculate_error_recovery_bonus(1, "error")
        10
        >>> calculate_error_recovery_bonus(1, "timeout")
        10
        >>> calculate_error_recovery_bonus(2, "success")
        0
    """
    # Recovery bonus if we just recovered from failure
    if consecutive_successes == 1 and previous_status in ["error", "timeout", "blocked"]:
        return 10
    return 0


def calculate_streak_bonus(current_streak: int) -> int:
    """Calculate XP bonus for maintaining a success streak.

    Rewards consecutive successful invocations:
    - +1 XP per consecutive success

    Args:
        current_streak: Number of consecutive successful invocations

    Returns:
        XP bonus equal to streak length

    Examples:
        >>> calculate_streak_bonus(1)
        1
        >>> calculate_streak_bonus(5)
        5
        >>> calculate_streak_bonus(25)
        25
    """
    return max(0, current_streak)


def calculate_total_xp_for_success(
    base_xp: int = 10,
    duration_seconds: float = 60.0,
    current_streak: int = 1,
    previous_status: str = "success",
    contribution_xp: int = 0,
) -> int:
    """Calculate total XP awarded for a successful invocation.

    Combines all XP sources:
    - Base XP for success
    - Speed bonus (if applicable)
    - Error recovery bonus (if applicable)
    - Contribution bonus (if any)
    - Streak bonus

    Args:
        base_xp: Base XP for successful invocation (default 10)
        duration_seconds: Duration in seconds (for speed bonus)
        current_streak: Current success streak length
        previous_status: Status of previous invocation
        contribution_xp: XP from specific contribution (from calculate_xp_for_contribution_type)

    Returns:
        Total XP to award

    Examples:
        >>> calculate_total_xp_for_success()
        11

        >>> calculate_total_xp_for_success(duration_seconds=25.0, current_streak=1, previous_status="error")
        31
    """
    total = base_xp
    total += calculate_speed_bonus(duration_seconds)
    total += calculate_error_recovery_bonus(current_streak, previous_status)
    total += contribution_xp
    total += calculate_streak_bonus(current_streak)
    return total


def get_level_thresholds() -> list[int]:
    """Get XP thresholds for each level.

    Returns a list where index i contains the minimum XP needed for level i+1.
    Uses a Fibonacci-like exponential progression:

    Level 1 (Intern):      0 XP
    Level 2 (Junior):      50 XP
    Level 3 (Mid-Level):   150 XP
    Level 4 (Senior):      400 XP
    Level 5 (Staff):       800 XP
    Level 6 (Principal):   1500 XP
    Level 7 (Distinguished): 3000 XP
    Level 8 (Fellow):      5000 XP

    Returns:
        List of XP thresholds in ascending order

    Examples:
        >>> get_level_thresholds()
        [0, 50, 150, 400, 800, 1500, 3000, 5000]
        >>> len(get_level_thresholds())
        8
    """
    return [0, 50, 150, 400, 800, 1500, 3000, 5000]


def get_level_title(level: int) -> str:
    """Get the title/rank name for a level.

    Args:
        level: Level number (1-8)

    Returns:
        Title string for the level

    Raises:
        ValueError: If level is outside valid range

    Examples:
        >>> get_level_title(1)
        'Intern'
        >>> get_level_title(8)
        'Fellow'
        >>> get_level_title(9)
        Traceback (most recent call last):
            ...
        ValueError: Level must be between 1 and 8, got 9
    """
    titles = {
        1: "Intern",
        2: "Junior",
        3: "Mid-Level",
        4: "Senior",
        5: "Staff",
        6: "Principal",
        7: "Distinguished",
        8: "Fellow",
    }

    if level < 1 or level > 8:
        raise ValueError(f"Level must be between 1 and 8, got {level}")

    return titles[level]


def calculate_level_from_xp(total_xp: int) -> int:
    """Calculate the current level based on total XP.

    Uses threshold comparison to find the appropriate level.

    Args:
        total_xp: Total XP accumulated

    Returns:
        Current level (1-8)

    Examples:
        >>> calculate_level_from_xp(0)
        1
        >>> calculate_level_from_xp(49)
        1
        >>> calculate_level_from_xp(50)
        2
        >>> calculate_level_from_xp(150)
        3
        >>> calculate_level_from_xp(5000)
        8
        >>> calculate_level_from_xp(10000)
        8
    """
    thresholds = get_level_thresholds()

    # Iterate backwards through thresholds to find current level
    for i in range(len(thresholds) - 1, -1, -1):
        if total_xp >= thresholds[i]:
            return i + 1

    # Should never reach here if thresholds are valid
    return 1


def calculate_xp_for_next_level(total_xp: int) -> int:
    """Calculate XP needed to reach the next level.

    Args:
        total_xp: Current total XP

    Returns:
        XP needed for next level (0 if already at max level)

    Examples:
        >>> calculate_xp_for_next_level(0)
        50
        >>> calculate_xp_for_next_level(49)
        1
        >>> calculate_xp_for_next_level(50)
        100
        >>> calculate_xp_for_next_level(5000)
        0
    """
    current_level = calculate_level_from_xp(total_xp)
    thresholds = get_level_thresholds()

    # If already at max level, no XP needed
    if current_level >= len(thresholds):
        return 0

    # Next threshold is at index current_level
    next_threshold = thresholds[current_level]
    return max(0, next_threshold - total_xp)


def calculate_xp_progress_in_level(total_xp: int) -> tuple[int, int]:
    """Calculate XP progress within the current level.

    Returns the current XP in the level and total XP needed for the level.

    Args:
        total_xp: Current total XP

    Returns:
        Tuple of (xp_in_current_level, xp_needed_for_level)

    Examples:
        >>> calculate_xp_progress_in_level(0)
        (0, 50)
        >>> calculate_xp_progress_in_level(25)
        (25, 50)
        >>> calculate_xp_progress_in_level(50)
        (0, 100)
        >>> calculate_xp_progress_in_level(100)
        (50, 100)
    """
    current_level = calculate_level_from_xp(total_xp)
    thresholds = get_level_thresholds()

    # Get the XP range for the current level
    level_start = thresholds[current_level - 1]

    # Get the next level's threshold (if it exists)
    if current_level < len(thresholds):
        level_end = thresholds[current_level]
    else:
        # Already at max level
        return (0, 0)

    xp_in_level = total_xp - level_start
    xp_needed_for_level = level_end - level_start

    return (xp_in_level, xp_needed_for_level)


def update_streak(
    previous_streak: int,
    previous_status: str,
    current_status: str,
    best_streak: int,
) -> tuple[int, int]:
    """Update success streak based on invocation outcome.

    Maintains both current streak (resets on failure) and best streak (all-time high).

    Args:
        previous_streak: Current streak before this invocation
        previous_status: Status of the previous invocation
        current_status: Status of the current invocation
        best_streak: Best streak achieved so far

    Returns:
        Tuple of (new_current_streak, new_best_streak)

    Examples:
        >>> update_streak(0, "success", "success", 0)
        (1, 1)
        >>> update_streak(1, "success", "success", 1)
        (2, 2)
        >>> update_streak(2, "success", "error", 2)
        (0, 2)
        >>> update_streak(5, "success", "timeout", 5)
        (0, 5)
    """
    if current_status == "success":
        # Increment streak
        new_streak = previous_streak + 1
        new_best = max(best_streak, new_streak)
        return (new_streak, new_best)
    else:
        # Failure resets current streak but keeps best streak
        return (0, best_streak)
