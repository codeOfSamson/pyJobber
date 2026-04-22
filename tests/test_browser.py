# tests/test_browser.py
import time
from browser.browser import human_delay, USER_AGENTS


def test_user_agents_not_empty():
    assert len(USER_AGENTS) >= 2
    for ua in USER_AGENTS:
        assert "Mozilla" in ua


def test_human_delay_sleeps_within_range():
    start = time.time()
    human_delay(0.01, 0.02)
    elapsed = time.time() - start
    assert 0.01 <= elapsed < 0.5
