from pathlib import Path
import pytest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "rust-standalone.yml"
PYTHON_WORKFLOW = ROOT / ".github" / "workflows" / "release-runtimes.yml"

pytestmark = pytest.mark.skipif(
    not WORKFLOW.exists(),
    reason="Rust workflow file not present (bundle install – source checkout required)",
)


def test_rust_macos_release_requires_real_apple_signing() -> None:
    """Tagged releases must require Developer ID signing and notarization."""
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "Require Apple release credentials" in workflow
    assert "APPLE_CERTIFICATE_P12_BASE64" in workflow
    assert "APPLE_CERTIFICATE_PASSWORD" in workflow
    assert "APPLE_SIGNING_IDENTITY" in workflow
    assert "APPLE_ID" in workflow
    assert "APPLE_TEAM_ID" in workflow
    assert "APPLE_APP_SPECIFIC_PASSWORD" in workflow
    assert 'codesign --force --sign "$APPLE_SIGNING_IDENTITY"' in workflow
    assert "--options runtime --timestamp" in workflow
    assert "Ad-hoc sign macOS .app (no Developer ID credentials)" not in workflow
    assert "Add allow-macos.sh to macOS release bundle" not in workflow
    assert "steps.apple-creds.outputs.available != 'true'" not in workflow


def test_python_release_ignores_rust_release_tags() -> None:
    workflow = PYTHON_WORKFLOW.read_text(encoding="utf-8")

    assert (
        "github.event_name == 'workflow_dispatch' || (github.event_name == 'release' "
        "&& startsWith(github.event.release.tag_name, 'v'))"
    ) in workflow


def test_rust_macos_release_is_notarized_and_gatekeeper_assessed() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "PRIORIS.app/Contents/MacOS/prioris" in workflow
    assert "xcrun notarytool submit" in workflow
    assert "xcrun stapler staple" in workflow
    assert "xcrun stapler validate" in workflow
    assert "spctl --assess --type execute" in workflow


def test_rust_macos_launcher_does_not_bypass_quarantine() -> None:
    launcher = (ROOT / "rust" / "scripts" / "run.sh").read_text(encoding="utf-8")
    self_test = (ROOT / "rust" / "scripts" / "self-test.sh").read_text(
        encoding="utf-8"
    )

    assert "PRIORIS.app/Contents/MacOS/prioris" in launcher
    assert "PRIORIS.app/Contents/MacOS/prioris" in self_test
    assert "com.apple.quarantine" not in launcher
    assert "com.apple.quarantine" not in self_test
