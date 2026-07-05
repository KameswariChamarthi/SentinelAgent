import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.disk_monitor import _health_score, growth_trend, list_local_drives


def test_health_score_full_disk_is_zero():
    assert _health_score(free=0, total=100) == 0


def test_health_score_40pct_free_is_100():
    assert _health_score(free=40, total=100) == 100


def test_health_score_clamped_at_100():
    assert _health_score(free=90, total=100) == 100


def test_health_score_zero_total_is_zero():
    assert _health_score(free=0, total=0) == 0


def test_growth_trend_needs_two_samples():
    assert growth_trend([(0, 100)]) == 0.0


def test_growth_trend_basic():
    # 1 day apart, used grew by 86400 * 2 bytes -> 2 bytes/sec * 86400 = rate/day
    samples = [(0, 1000), (86400, 1000 + 500)]
    rate = growth_trend(samples)
    assert abs(rate - 500) < 1e-6


def test_list_local_drives_returns_at_least_one():
    drives = list_local_drives()
    assert len(drives) >= 1
