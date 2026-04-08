from agent.storage.db import get_agent_state, count_pending_blocks
from agent.sync.client import sync_state


def get_health():
    paused, reason = get_agent_state()

    return {
        "paused": paused,
        "pause_reason": reason,
        "last_sync": sync_state.last_success_ts,
        "failures": sync_state.consecutive_failures,
        "backing_off": not sync_state.can_attempt(),
        "pending_blocks": count_pending_blocks(),
    }
