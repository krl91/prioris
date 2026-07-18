from pathlib import Path
import pytest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "rust-standalone.yml"

pytestmark = pytest.mark.skipif(
    not WORKFLOW.exists(),
    reason="Rust workflow file not present (bundle install – source checkout required)",
)


def test_rust_macos_release_requires_real_apple_signing() -> None:
    """Developer ID signing must be the primary release path.

    Ad-hoc signing (--sign -) is allowed only as a fallback conditioned on
    Apple credentials being absent (steps.apple-creds.outputs.available != 'true').
    The credential-detection step and the Developer ID signing path must always
    be present.
    """
    workflow = WORKFLOW.read_text(encoding="utf-8")

    # Credential check and Developer ID path must always be present
    assert "APPLE_CERTIFICATE_P12_BASE64" in workflow
    assert "APPLE_SIGNING_IDENTITY" in workflow
    assert 'codesign --force --sign "$APPLE_SIGNING_IDENTITY"' in workflow
    assert "--options runtime --timestamp" in workflow
    # Any ad-hoc fallback must be gated on credentials being unavailable
    assert "steps.apple-creds.outputs.available != 'true'" in workflow, (
        "Workflow must include a conditional ad-hoc fallback gated on "
        "Apple credentials being absent."
    )


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
