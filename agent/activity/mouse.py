from pynput import mouse
from agent.utils.logger import get_logger

log = get_logger("mouse")

class MouseTracker:
    def __init__(self):
        self.clicks = 0
        self.distance = 0
        self._last_pos = None

        self.listener = mouse.Listener(
            on_move=self.on_move,
            on_click=self.on_click
        )

    def on_move(self, x, y):
        if self._last_pos:
            dx = x - self._last_pos[0]
            dy = y - self._last_pos[1]
            self.distance += (dx**2 + dy**2) ** 0.5
        self._last_pos = (x, y)

    def on_click(self, x, y, button, pressed):
        if pressed:
            self.clicks += 1

    def start(self):
        log.info("Mouse tracker started")
        self.listener.start()

    def reset(self):
        data = {
            "clicks": self.clicks,
            "distance": int(self.distance)
        }
        self.clicks = 0
        self.distance = 0
        return data
