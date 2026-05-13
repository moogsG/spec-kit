"""Tests for check-prerequisites with ticket branch workflow."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.conftest import requires_bash

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COMMON_SH = PROJECT_ROOT / "scripts" / "bash" / "common.sh"
CHECK_PREREQ_SH = PROJECT_ROOT / "scripts" / "bash" / "check-prerequisites.sh"
COMMON_PS = PROJECT_ROOT / "scripts" / "powershell" / "common.ps1"
CHECK_PREREQ_PS = PROJECT_ROOT / "scripts" / "powershell" / "check-prerequisites.ps1"

HAS_PWSH = shutil.which("pwsh") is not None
_POWERSHELL = shutil.which("powershell.exe") or shutil.which("powershell")


def _clean_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("SPECIFY_"):
            env.pop(key)
    return env


def _git_init(repo: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init", "-q"], cwd=repo, check=True)


def _install_bash_scripts(repo: Path) -> None:
    scripts = repo / ".specify" / "scripts" / "bash"
    scripts.mkdir(parents=True, exist_ok=True)
    shutil.copy(COMMON_SH, scripts / "common.sh")
    shutil.copy(CHECK_PREREQ_SH, scripts / "check-prerequisites.sh")


def _install_ps_scripts(repo: Path) -> None:
    scripts = repo / ".specify" / "scripts" / "powershell"
    scripts.mkdir(parents=True, exist_ok=True)
    shutil.copy(COMMON_PS, scripts / "common.ps1")
    shutil.copy(CHECK_PREREQ_PS, scripts / "check-prerequisites.ps1")


@pytest.fixture
def prereq_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "proj"
    repo.mkdir()
    _git_init(repo)
    (repo / ".specify").mkdir()
    _install_bash_scripts(repo)
    _install_ps_scripts(repo)
    return repo


def _make_feature(repo: Path, feature_dir: str = "specs/GDEV-1234-add-login") -> Path:
    feat = repo / feature_dir
    feat.mkdir(parents=True, exist_ok=True)
    (feat / "spec.md").write_text("# spec\n", encoding="utf-8")
    (feat / "plan.md").write_text("# plan\n", encoding="utf-8")
    return feat


@requires_bash
def test_check_prerequisites_accepts_ticket_branch(prereq_repo: Path) -> None:
    subprocess.run(["git", "checkout", "-q", "-b", "feature/GDEV-1234"], cwd=prereq_repo, check=True)
    feat = _make_feature(prereq_repo)

    script = prereq_repo / ".specify" / "scripts" / "bash" / "check-prerequisites.sh"
    result = subprocess.run(
        ["bash", str(script), "--json"],
        cwd=prereq_repo,
        capture_output=True,
        text=True,
        check=False,
        env=_clean_env(),
    )

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["FEATURE_DIR"] == str(feat)


@requires_bash
def test_check_prerequisites_skips_branch_validation_when_feature_json_matches(
    prereq_repo: Path,
) -> None:
    subprocess.run(["git", "checkout", "-q", "-b", "feature/custom-branch"], cwd=prereq_repo, check=True)
    feat = _make_feature(prereq_repo, "specs/custom-feature")
    (prereq_repo / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/custom-feature"}),
        encoding="utf-8",
    )

    script = prereq_repo / ".specify" / "scripts" / "bash" / "check-prerequisites.sh"
    result = subprocess.run(
        ["bash", str(script), "--json"],
        cwd=prereq_repo,
        capture_output=True,
        text=True,
        check=False,
        env=_clean_env(),
    )

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["FEATURE_DIR"] == str(feat)


@requires_bash
def test_check_prerequisites_rejects_invalid_branch_without_feature_json(
    prereq_repo: Path,
) -> None:
    subprocess.run(["git", "checkout", "-q", "-b", "feature/custom-branch"], cwd=prereq_repo, check=True)

    script = prereq_repo / ".specify" / "scripts" / "bash" / "check-prerequisites.sh"
    result = subprocess.run(
        ["bash", str(script), "--json"],
        cwd=prereq_repo,
        capture_output=True,
        text=True,
        check=False,
        env=_clean_env(),
    )

    assert result.returncode != 0
    assert "Not on a feature branch" in result.stderr


@pytest.mark.skipif(not (HAS_PWSH or _POWERSHELL), reason="no PowerShell available")
def test_check_prerequisites_ps_skips_branch_validation_when_feature_json_matches(
    prereq_repo: Path,
) -> None:
    subprocess.run(["git", "checkout", "-q", "-b", "feature/custom-branch"], cwd=prereq_repo, check=True)
    feat = _make_feature(prereq_repo, "specs/ps-custom-feature")
    (prereq_repo / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/ps-custom-feature"}),
        encoding="utf-8",
    )

    script = prereq_repo / ".specify" / "scripts" / "powershell" / "check-prerequisites.ps1"
    exe = "pwsh" if HAS_PWSH else _POWERSHELL
    result = subprocess.run(
        [exe, "-NoProfile", "-File", str(script), "-Json"],
        cwd=prereq_repo,
        capture_output=True,
        text=True,
        check=False,
        env=_clean_env(),
    )

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["FEATURE_DIR"] == str(feat)
