"""One toast per job: raised once, updated in place, closed on finish.

These test the BEHAVIOUR Nick asked for (2026-08-22), not Textual's
internals — count the toasts on screen and read what they say.

``run_test`` disables notifications by default, so every test here opts
back in. (That default is also why ``JobToasts`` must degrade quietly
when there is no toast to update: the rest of the suite runs without a
toast rack at all.)"""

from textual.app import App, ComposeResult
from textual.widgets import Label
from textual.widgets._toast import Toast

from mediasmith import progress


class Host(App):
    """Bare app with a JobToasts, the way DetailsView owns one."""

    def compose(self) -> ComposeResult:
        yield Label("host")

    def on_mount(self) -> None:
        self.jobs = progress.JobToasts(self)


def toasts(app) -> list[str]:
    return [t._notification.message for t in app.query(Toast)]


async def test_one_job_keeps_one_toast_and_updates_it():
    app = Host()
    async with app.run_test(notifications=True) as pilot:
        app.jobs.report("j", "get subs", "fetching…")
        await pilot.pause()
        assert toasts(app) == ["fetching…"]
        app.jobs.report("j", "get subs", "searching providers…")
        await pilot.pause()
        assert toasts(app) == ["searching providers…"]   # replaced, not added
        app.jobs.report("j", "get subs", "downloading…")
        await pilot.pause()
        assert toasts(app) == ["downloading…"]


async def test_the_toast_outlives_the_default_notification_timeout():
    """The bug: each message's toast faded before the next arrived."""
    app = Host()
    async with app.run_test(notifications=True) as pilot:
        app.jobs.report("j", "get subs", "fetching…")
        await pilot.pause(0.2)
        assert app.NOTIFICATION_TIMEOUT <= progress.RUNNING_TIMEOUT
        toast = app.query_one(Toast)
        assert toast._notification.timeout == progress.RUNNING_TIMEOUT
        assert toast._notification.time_left > 60


async def test_finishing_releases_the_toast_to_expire():
    app = Host()
    async with app.run_test(notifications=True) as pilot:
        app.jobs.report("j", "get subs", "fetching…")
        await pilot.pause()
        app.jobs.report("j", "get subs", "3 subtitles installed",
                        done=True, timeout=0.05)
        await pilot.pause()
        assert toasts(app) == ["3 subtitles installed"]
        await pilot.pause(0.3)
        assert toasts(app) == []            # gone once the job is over


async def test_two_jobs_get_two_toasts():
    app = Host()
    async with app.run_test(notifications=True) as pilot:
        app.jobs.report("a", "get subs", "one.mkv: fetching…")
        app.jobs.report("b", "get subs", "two.mkv: fetching…")
        await pilot.pause()
        assert toasts(app) == ["one.mkv: fetching…", "two.mkv: fetching…"]
        app.jobs.report("a", "get subs", "one.mkv: done", done=True)
        await pilot.pause()
        assert toasts(app) == ["one.mkv: done", "two.mkv: fetching…"]


async def test_a_report_after_finishing_raises_a_new_toast():
    """A second run of the same job is a new job, not a resurrection."""
    app = Host()
    async with app.run_test(notifications=True) as pilot:
        app.jobs.report("j", "folderize", "organizing…")
        app.jobs.report("j", "folderize", "12 moved", done=True, timeout=0.05)
        await pilot.pause(0.3)
        app.jobs.report("j", "folderize", "organizing…")
        await pilot.pause()
        assert toasts(app) == ["organizing…"]


async def test_severity_change_restyles_the_live_toast():
    app = Host()
    async with app.run_test(notifications=True) as pilot:
        app.jobs.report("j", "get subs", "fetching…")
        await pilot.pause()
        app.jobs.report("j", "get subs", "no subtitles found",
                        severity="warning", done=True)
        await pilot.pause()
        toast = app.query_one(Toast)
        assert toast.has_class("-warning") and not toast.has_class(
            "-information")


async def test_a_dismissed_toast_does_not_swallow_the_next_message():
    """Clicking a toast away removes it; the job keeps talking."""
    app = Host()
    async with app.run_test(notifications=True) as pilot:
        app.jobs.report("j", "get subs", "fetching…")
        await pilot.pause()
        app.query_one(Toast)._expire()          # what a click does
        await pilot.pause()
        assert toasts(app) == []
        app.jobs.report("j", "get subs", "downloading…")
        await pilot.pause()
        assert toasts(app) == ["downloading…"]
