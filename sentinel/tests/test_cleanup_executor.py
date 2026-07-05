import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from models.schemas import Recommendation, ScanTargetResult
from services.cleanup_executor import execute_recommendation
from utils.safety_rules import ConfidenceLevel


def _make_target(tmp_path: Path) -> ScanTargetResult:
    fake_cache_dir = tmp_path / "AppData" / "Local" / "Temp"
    fake_cache_dir.mkdir(parents=True)
    (fake_cache_dir / "a.tmp").write_bytes(b"x" * 1024)
    (fake_cache_dir / "b.tmp").write_bytes(b"y" * 2048)
    return ScanTargetResult(
        category="user_temp",
        display_name="User Temp",
        paths=[str(fake_cache_dir)],
        size_bytes=3072,
        confidence=ConfidenceLevel.HIGH,
        file_count=2,
    )


def test_execution_refused_without_approval(tmp_path):
    target = _make_target(tmp_path)
    rec = Recommendation(target=target, approved=False)
    with pytest.raises(ValueError):
        execute_recommendation(rec)
    # Files must still exist -- nothing was touched.
    assert (Path(target.paths[0]) / "a.tmp").exists()


def test_execution_refused_when_pending(tmp_path):
    target = _make_target(tmp_path)
    rec = Recommendation(target=target, approved=None)
    with pytest.raises(ValueError):
        execute_recommendation(rec)


def test_execution_succeeds_when_approved(tmp_path):
    target = _make_target(tmp_path)
    rec = Recommendation(target=target, approved=True)
    result = execute_recommendation(rec)
    assert result.bytes_freed == 3072
    assert not Path(target.paths[0]).exists()
    assert result.errors == []


def test_execution_refuses_protected_path_even_if_approved():
    # Even with approved=True, a path matching NEVER_TOUCH must be refused.
    target = ScanTargetResult(
        category="malicious_test",
        display_name="Fake protected target",
        paths=[r"C:\Users\Someone\Documents\important.docx"],
        size_bytes=100,
        confidence=ConfidenceLevel.HIGH,
        file_count=1,
    )
    rec = Recommendation(target=target, approved=True)
    result = execute_recommendation(rec)
    assert result.bytes_freed == 0
    assert any("REFUSED" in e for e in result.errors)
