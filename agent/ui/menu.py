import rumps
import requests
import socket

from agent.health import get_health
from agent.storage.db import set_agent_state
from agent.security.keychain import (
    get_user_session,
    set_user_session,
    clear_user_session,
    get_device_token,
    set_device_token,
)

API_BASE = "http://127.0.0.1:8000"


class TrackerMenu(rumps.App):
    def __init__(self):
        super().__init__("Apidots", icon=None, quit_button=None)

        # Persistent menu items
        self.status_item = rumps.MenuItem("Loading…")

        self.login_item = rumps.MenuItem("Sign in to Apidots", self.open_login)
        self.pause_item = rumps.MenuItem("Pause tracking", self.pause)
        self.resume_item = rumps.MenuItem("Resume tracking", self.resume)
        self.logout_item = rumps.MenuItem("Logout", self.logout)
        self.logs_item = rumps.MenuItem("Open logs", self.open_logs)
        self.quit_item = rumps.MenuItem("Quit", self.quit)

        # Timer for status refresh
        self.timer = rumps.Timer(self.update_status, 5)
        self.timer.start()

        self.refresh_menu()

    # ------------------------------------------------------------------
    # MENU RENDERING
    # ------------------------------------------------------------------

    def refresh_menu(self):
        self.menu.clear()

        if not self.user_logged_in():
            self.title = "⚪ Apidots"
            self.menu.add(self.login_item)
            self.menu.add(None)
            self.menu.add(self.quit_item)
            return

        health = get_health()

        self.status_item.title = (
            "⏸ Tracking paused" if health["paused"] else "🟢 Tracking active"
        )
        self.title = "⏸ Apidots" if health["paused"] else "🟢 Apidots"

        self.menu.add(self.status_item)
        self.menu.add(None)

        if health["paused"]:
            self.menu.add(self.resume_item)
        else:
            self.menu.add(self.pause_item)

        self.menu.add(None)
        self.menu.add(self.logout_item)
        self.menu.add(self.logs_item)
        self.menu.add(None)
        self.menu.add(self.quit_item)

    # ------------------------------------------------------------------
    # STATUS UPDATES
    # ------------------------------------------------------------------

    def update_status(self, _):
        if not self.user_logged_in():
            return
        self.refresh_menu()

    # ------------------------------------------------------------------
    # AUTH
    # ------------------------------------------------------------------

    def open_login(self, _):
        email_prompt = rumps.Window(
            title="Apidots Login",
            message="Enter your username",
            ok="Next",
            cancel="Cancel",
        )
        email_resp = email_prompt.run()
        if not email_resp.clicked:
            return

        password_prompt = rumps.Window(
            title="Apidots Login",
            message="Enter your password",
            ok="Login",
            cancel="Cancel",
            secure=True,
        )
        pass_resp = password_prompt.run()
        if not pass_resp.clicked:
            return

        self.authenticate(email_resp.text.strip(), pass_resp.text.strip())

    def authenticate(self, email, password):
        try:
            r = requests.post(
                f"{API_BASE}/api/auth/login/",
                json={"username": email, "password": password},
                timeout=10,
            )
        except Exception:
            rumps.alert("Cannot reach server")
            return

        if r.status_code != 200:
            rumps.alert("Login failed")
            return

        data = r.json()
        set_user_session(data["access"], data["refresh"])
        self.ensure_device_registered()
        self.refresh_menu()

    def logout(self, _):
        clear_user_session()
        self.refresh_menu()

    def user_logged_in(self):
        session = get_user_session()
        return bool(session.get("access"))

    # ------------------------------------------------------------------
    # DEVICE REGISTRATION
    # ------------------------------------------------------------------

    def ensure_device_registered(self):
        try:
            get_device_token()
            return
        except RuntimeError:
            pass

        session = get_user_session()
        headers = {"Authorization": f"Bearer {session['access']}"}

        r = requests.post(
            f"{API_BASE}/api/devices/register/",
            headers=headers,
            json={"hostname": socket.gethostname()},
            timeout=10,
        )

        if r.status_code != 201:
            rumps.alert("Device registration failed")
            return

        set_device_token(r.json()["device_token"])

    # ------------------------------------------------------------------
    # TRACKING CONTROLS
    # ------------------------------------------------------------------

    def pause(self, _):
        response = rumps.Window(
            title="Pause tracking",
            message="Why are you pausing tracking?",
            ok="Pause",
            cancel="Cancel",
        ).run()

        if not response.clicked:
            return

        reason = response.text.strip() or "No reason provided"

        if self.send_pause_event(True, reason):
            set_agent_state(True, reason)
            self.refresh_menu()


    def resume(self, _):
        set_agent_state(False, None)
        self.send_pause_event(False, None)
        self.refresh_menu()

    def send_pause_event(self, paused, reason):
        session = get_user_session()
        device_token = get_device_token()

        headers = {
            "X-DEVICE-TOKEN": device_token,
        }

        r = requests.post(
            f"{API_BASE}/api/audit/pause/",
            json={"paused": paused, "reason": reason},
            headers=headers,
            timeout=10,
        )

        if r.status_code != 201:
            rumps.alert("Failed to sync pause state")
            return False

        return True


    # ------------------------------------------------------------------
    # MISC
    # ------------------------------------------------------------------

    def open_logs(self, _):
        import subprocess
        from agent.paths import AGENT_LOG
        subprocess.call(["open", "-a", "Console", str(AGENT_LOG)])

    def quit(self, _):
        rumps.quit_application()


if __name__ == "__main__":
    TrackerMenu().run()
