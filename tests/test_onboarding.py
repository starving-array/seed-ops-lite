"""Unit tests for first-time user onboarding guided tours, progress trackers, and sample schemas."""

from app.platform.configuration.settings import platform_settings
from app.services.onboarding import TOUR_STEPS, OnboardingManager


def test_onboarding_configurations_loading() -> None:
    """Verify PlatformSettings onboarding parameters loaded correctly."""
    assert platform_settings.PLATFORM_ONBOARDING_MAX_STEPS == 15
    assert platform_settings.PLATFORM_ONBOARDING_AUTO_LAUNCH is True
    assert platform_settings.PLATFORM_ONBOARDING_SAMPLE_SIZE == 100
    assert platform_settings.PLATFORM_ONBOARDING_HINT_LIMIT == 5


def test_welcome_screen_dismissal() -> None:
    """Verify welcome preference dismisses properly."""
    mgr = OnboardingManager()

    init_state = mgr.initialize_onboarding()
    assert init_state["autoLaunch"] is True
    assert init_state["welcomeDismissed"] is False

    # Dismiss welcome overlay
    mgr.dismiss_welcome()

    new_state = mgr.initialize_onboarding()
    assert new_state["autoLaunch"] is False
    assert new_state["welcomeDismissed"] is True


def test_guided_tour_navigation_and_progress() -> None:
    """Verify walkthrough tracker navigates and registers step completions."""
    mgr = OnboardingManager()

    mgr.tracker.start_tour()
    steps = mgr.get_tour_steps()
    assert len(steps) == len(TOUR_STEPS)

    # Complete welcome step
    mgr.tracker.complete_step("welcome")
    assert mgr.tracker.progress.last_viewed_step_id == "welcome"
    assert "welcome" in mgr.tracker.progress.completed_step_ids

    # Skip next schema designer step
    mgr.tracker.skip_step("schema-designer")
    assert mgr.tracker.progress.last_viewed_step_id == "schema-designer"
    assert "schema-designer" in mgr.tracker.progress.skipped_step_ids


def test_sample_project_generation() -> None:
    """Verify sample project provider generates valid schema tables and relationships."""
    mgr = OnboardingManager()

    schema = mgr.create_sample_project()
    assert len(schema.tables) == 4
    assert len(schema.relationships) == 2
    assert mgr.stats.sample_projects_created == 1

    # Verify tables structures
    users_table = next(t for t in schema.tables if t.id == "users")
    assert any(c.id == "email" for c in users_table.columns)


def test_tour_completion_and_metrics() -> None:
    """Verify tours skip and completion steps metrics are updated."""
    mgr = OnboardingManager()

    mgr.tracker.start_tour()
    mgr.complete_tour()
    assert mgr.tracker.progress.is_tour_completed is True
    assert mgr.stats.tours_completed == 1

    mgr.skip_tour()
    assert mgr.stats.tours_skipped == 1
