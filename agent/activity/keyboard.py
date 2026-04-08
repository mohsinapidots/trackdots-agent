from pynput import keyboard
from agent.utils.logger import get_logger

log = get_logger("keyboard")

class KeyboardTracker:
    def __init__(self):
        self.count = 0
        self.listener = keyboard.Listener(on_press=self.on_press)

    def on_press(self, key):
        self.count += 1

    def start(self):
        log.info("Keyboard tracker started")
        self.listener.start()

    def reset(self):
        c = self.count
        self.count = 0
        return c
