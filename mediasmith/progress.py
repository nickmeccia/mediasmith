"""One toast per running job — raised on its first report, updated in
place, dismissed only when the job ends.

Nick, 2026-08-22: "fetch subtitles" and "download posters" each announced
themselves in a toast that had faded before the next message arrived, so
a five-second job read as a dead keypress. A job now owns ONE toast for
its whole life: every report replaces the text in the toast already on
screen, and the toast leaves when the job does.

Textual 8.2.8 has no public "update this notification" API — but it does
not need one. A ``Notification`` is a mutable dataclass with a stable
``identity``, ``Toast.render`` reads its notification live, and
``ToastRack.show`` reconciles by identity. So an update is a mutation
plus a refresh of the one toast holding it, and a dismissal is
``_unnotify`` plus a rack refresh.

Those are private names, so every reach into them is guarded: if a later
Textual moves them, ``JobToasts`` degrades to ordinary one-shot
notifications and nothing raises. `tests/test_progress.py` pins the
behaviour that matters (one toast, updated, closed on finish) rather
than the internals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import time

from textual.notifications import Notification, Notify

FINAL_TIMEOUT = 8.0
"""How long the finished job's toast lingers with its result."""

RUNNING_TIMEOUT = 3600.0
"""A running job's toast must not expire on its own — the job closes it.
Textual reaps notifications by wall clock and `Toast` sets its removal
timer at mount, so 'does not expire' is spelled as an hour."""


@dataclass
class JobToast:
    """A single job's toast. Create through ``JobToasts.report``."""

    app: object
    notification: Notification
    done: bool = False

    def _toast(self):
        """The mounted Toast showing this job, or None.

        None is the ordinary answer, not a failure: a clicked-away toast
        is gone, and ``run_test`` mounts no toast rack at all."""
        from textual.widgets._toast import Toast, ToastRack
        try:
            rack = self.app.screen.get_child_by_type(ToastRack)
            holder = rack.get_child_by_id(
                ToastRack._toast_id(self.notification))
            return holder.query_one(Toast)
        except Exception:
            return None

    def update(self, message: str, severity: str | None = None) -> bool:
        """Replace the text in the toast on screen. False if it is gone
        (dismissed by a click, or never mounted) — the caller then raises
        a fresh one."""
        toast = self._toast()
        if toast is None:
            return False
        self.notification.message = message
        if severity is not None and severity != self.notification.severity:
            # severity is a CSS class on the toast, set at construction
            toast.remove_class(f"-{self.notification.severity}")
            toast.add_class(f"-{severity}")
            self.notification.severity = severity
        toast.refresh(layout=True)
        return True

    def finish(self, timeout: float = FINAL_TIMEOUT) -> None:
        """Let the toast expire normally now that the job is over."""
        self.done = True
        toast = self._toast()
        if toast is None:
            return
        self.notification.timeout = timeout
        self.notification.raised_at = time()
        toast.set_timer(timeout, toast._expire)

    def dismiss(self) -> None:
        """Take the toast down immediately."""
        self.done = True
        try:
            self.app._unnotify(self.notification)
        except Exception:
            pass


@dataclass
class JobToasts:
    """The live jobs of one view, keyed by whatever identifies a job.

    The key is the caller's: a title alone where a job cannot overlap
    itself ("folderize"), title + path where it can (subtitle fetches and
    conversions run side by side on purpose).
    """

    app: object
    _live: dict[str, JobToast] = field(default_factory=dict)

    def report(self, key: str, title: str, message: str, *,
               severity: str = "information", done: bool = False,
               timeout: float = FINAL_TIMEOUT) -> None:
        """Say ``message`` on ``key``'s toast, raising it if this is the
        job's first word. ``done`` releases the toast to expire."""
        job = self._live.get(key)
        if job is not None and not job.done and job.update(message, severity):
            if done:
                job.finish(timeout)
                self._live.pop(key, None)
            return
        # no live toast (first report, expired, or clicked away): raise one
        notification = Notification(
            message, title, severity,          # type: ignore[arg-type]
            timeout if done else RUNNING_TIMEOUT, markup=False)
        job = JobToast(self.app, notification)
        try:
            self.app.post_message(Notify(notification))
        except Exception:
            return
        if done:
            job.done = True
        else:
            self._live[key] = job

    def dismiss(self, key: str) -> None:
        job = self._live.pop(key, None)
        if job is not None:
            job.dismiss()
