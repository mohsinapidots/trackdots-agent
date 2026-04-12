import uuid
import time
from agent.activity.idle import get_idle_seconds
from agent.system.active_app import get_active_app
from agent.activity.screenshot import capture_screenshot
from agent.storage.db import get_agent_state
from agent.utils.logger import get_logger

log = get_logger("block")

IDLE_THRESHOLD = 300  # 5 minutes


class ActivityBlock:
    def __init__(self, start_ts: float):
        self.start_ts       = start_ts
        self.keys           = 0
        self.mouse_clicks   = 0
        self.mouse_distance = 0
        self.apps           = {}
        self.idle           = False
        self.block_uuid     = str(uuid.uuid4())
        self.screenshot_path = None

    def add_activity(self, keys, mouse):
        self.keys           += keys
        self.mouse_clicks   += mouse["clicks"]
        self.mouse_distance += mouse["distance"]
        app = get_active_app()
        if app:
            name  = app["name"]
            title = app.get("window_title")
            self.apps[name] = self.apps.get(name, 0) + 1
            # Log whenever the active app or tab changes
            label = f"{name} | {title}" if title and title.lower() != name.lower() else name
            if label != getattr(self, '_last_label', None):
                log.info("App: %s", label)
                self._last_label = label

    def finalize(self):
        paused, _ = get_agent_state()
        if paused:
            self.idle            = True
            self.screenshot_path = None
        else:
            # A block is idle only if there was NO activity during it.
            # Checking system idle time at finalization is wrong — the user
            # may have been active earlier in the block and stopped at the end.
            has_activity = (self.keys > 0 or self.mouse_clicks > 0 or self.mouse_distance > 50)
            self.idle    = not has_activity

        # Capture screenshot — log error if it fails
        try:
            result = capture_screenshot()
            if result:
                self.screenshot_path = result["path"]
                log.info("Screenshot captured: %s", self.screenshot_path)
            else:
                log.warning("Screenshot capture returned None — Screen Recording permission may be missing")
                self.screenshot_path = None
        except Exception as e:
            log.error("Screenshot capture exception: %s", e)
            self.screenshot_path = None

        primary_app = max(self.apps, key=self.apps.get) if self.apps else None

        return {
            "start":           self.start_ts,
            "end":             time.time(),
            "idle":            self.idle,
            "keys":            self.keys,
            "mouse_clicks":    self.mouse_clicks,
            "mouse_distance":  self.mouse_distance,
            "screenshot_path": self.screenshot_path,
            "primary_app":     primary_app,
            "block_uuid":      self.block_uuid,
            "created_at":      time.time(),
        }