import time

class SyncState:
    def __init__(self):
        self.consecutive_failures = 0
        self.last_attempt_ts = None
        self.last_success_ts = None
        self.backoff_until = 0

    def record_attempt(self):
        self.last_attempt_ts = time.time()

    def record_success(self):
        self.consecutive_failures = 0
        self.last_success_ts = time.time()
        self.backoff_until = 0

    def record_failure(self, backoff_seconds):
        self.consecutive_failures += 1
        self.backoff_until = time.time() + backoff_seconds

    def can_attempt(self):
        return time.time() >= self.backoff_until
