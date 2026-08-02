"""Static contract for the separate Python macOS Intel release workflow."""
from pathlib import Path

import pytest


ROOT = Path(__file__).parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "python-macos-intel.yml"
NOTES = ROOT / ".github" / "release-notes" / "python-intel-latest.md"

pytestmark = pytest.mark.skipif(
    not WORKFLOW.exists(),
    reason="Python Intel workflow file not present (source checkout required)",
)


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_python_intel_workflow_is_isolated_and_native_x64() -> None:
    workflow = _workflow()
    assert 'tags:\n      - "python-intel-v*"' in workflow
    assert "runs-on: macos-15-intel" in workflow
    assert 'test "$(uname -m)" = "x86_64"' in workflow
    assert "-DCMAKE_OSX_ARCHITECTURES=x86_64" in workflow
    assert "-DCMAKE_OSX_DEPLOYMENT_TARGET=13.0" in workflow
    assert "lipo -archs runtime/macos-x64/llama-simple" in workflow


def test_python_intel_workflow_builds_a_pure_cli_llm_runtime() -> None:
    workflow = _workflow()
    assert "--target llama-simple" in workflow
    assert "@executable_path" in workflow
    assert "llama-server|ggml-rpc-server|llama-cli" in workflow
    assert "scripts/smoke_challenge_llm.py config.toml" in workflow
    assert "MODEL_SHA256" in workflow


def test_python_intel_workflow_tests_the_extracted_offline_bundle() -> None:
    workflow = _workflow()
    assert "./scripts/install_unix.sh" in workflow
    assert ".venv/bin/python -m pytest" in workflow
    assert "runtime/macos-x64/llama-simple" in workflow
    assert "ObsidianVault" in workflow
    assert "tkinter.Tcl()" in workflow


def test_python_intel_release_has_dedicated_assets_and_notes() -> None:
    workflow = _workflow()
    notes = NOTES.read_text(encoding="utf-8")
    assert "prioris-python-intel-v$version-macos-x64" in workflow
    assert "runtime-macos-x64.zip" in workflow
    assert "prerelease: true" in workflow
    assert "make_latest: false" in workflow
    assert "prioris-python-intel-__VERSION__-macos-x64.zip" in notes
