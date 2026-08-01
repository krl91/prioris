from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "rust-macos-intel.yml"

pytestmark = pytest.mark.skipif(
    not WORKFLOW.exists(),
    reason="Intel Rust workflow file not present (source checkout required)",
)


def test_intel_workflow_uses_a_dedicated_x64_runner_and_tag() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert '"rust-intel-v*"' in workflow
    assert "runs-on: macos-15-intel" in workflow
    assert 'test "$(uname -m)" = "x86_64"' in workflow
    assert workflow.count('lipo -archs') >= 3
    assert "Mach-O 64-bit executable x86_64" in workflow


def test_intel_workflow_builds_and_tests_the_standalone_llm_bundle() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "cargo test --locked --release --bin prioris" in workflow
    assert "cargo build --locked --release --features embedded-llm,accelerate" in workflow
    assert "Contents/Resources/models" in workflow
    assert "--runtime-smoke" in workflow
    assert "--llm-smoke" in workflow
    assert "ObsidianVault" in workflow


def test_intel_workflow_supports_both_apple_signing_modes() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "Partial Apple credential set" in workflow
    assert "Sign Intel application with Developer ID" in workflow
    assert "Ad-hoc sign Intel application without Apple credentials" in workflow
    assert "xcrun notarytool submit" in workflow
    assert "xcrun stapler staple" in workflow
    assert "codesign --verify --deep --strict" in workflow
