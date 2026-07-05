import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.safety_rules import (
    ConfidenceLevel,
    classify_confidence,
    filter_candidates,
    is_path_protected,
)


def test_documents_is_protected():
    assert is_path_protected(r"C:\Users\Alice\Documents\resume.docx")


def test_desktop_is_protected():
    assert is_path_protected(r"C:\Users\Alice\Desktop\important.txt")


def test_system32_is_protected():
    assert is_path_protected(r"C:\Windows\System32\kernel32.dll")


def test_program_files_is_protected():
    assert is_path_protected(r"C:\Program Files\SomeApp\app.exe")


def test_windows_temp_is_not_protected():
    assert not is_path_protected(r"C:\Windows\Temp\some_temp_file.tmp")


def test_recycle_bin_is_not_protected():
    assert not is_path_protected(r"C:\$Recycle.Bin\S-1-5-21-abc\file.txt")


def test_unknown_path_defaults_to_protected():
    verdict = classify_confidence(r"C:\Users\Alice\SomeRandomFolder\stuff.dat")
    assert verdict.protected is True
    assert verdict.confidence == ConfidenceLevel.DANGEROUS


def test_chrome_cache_is_high_confidence():
    verdict = classify_confidence(
        r"C:\Users\Alice\AppData\Local\Google\Chrome\User Data\Default\Cache\file"
    )
    assert verdict.protected is False
    assert verdict.confidence == ConfidenceLevel.HIGH


def test_node_modules_is_moderate_confidence():
    verdict = classify_confidence(r"C:\Users\Alice\project\node_modules\lodash")
    assert verdict.protected is False
    assert verdict.confidence == ConfidenceLevel.MODERATE


def test_appdata_credentials_is_protected_even_though_appdata_local_is_common():
    assert is_path_protected(
        r"C:\Users\Alice\AppData\Local\Microsoft\Credentials\secret"
    )


def test_filter_candidates_drops_protected_paths():
    candidates = [
        r"C:\Users\Alice\Documents\resume.docx",   # protected
        r"C:\Windows\Temp\a.tmp",                    # safe
        r"C:\Users\Alice\Desktop\photo.png",          # protected
    ]
    result = filter_candidates(candidates)
    paths = [v.path for v in result]
    assert r"C:\Windows\Temp\a.tmp" in paths
    assert r"C:\Users\Alice\Documents\resume.docx" not in paths
    assert r"C:\Users\Alice\Desktop\photo.png" not in paths
