from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "rust-standalone.yml"


def test_rust_macos_release_requires_real_apple_signing() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "APPLE_CERTIFICATE_P12_BASE64" in workflow
    assert "APPLE_SIGNING_IDENTITY" in workflow
    assert 'codesign --force --sign "$APPLE_SIGNING_IDENTITY"' in workflow
    assert "--options runtime --timestamp" in workflow
    assert "codesign --force --sign -" not in workflow


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
