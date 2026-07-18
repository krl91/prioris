from pathlib import Path
import pytest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "rust-standalone.yml"
PYTHON_WORKFLOW = ROOT / ".github" / "workflows" / "release-runtimes.yml"

pytestmark = pytest.mark.skipif(
    not WORKFLOW.exists(),
    reason="Rust workflow file not present (bundle install – source checkout required)",
)


def test_rust_macos_release_supports_both_signing_modes() -> None:
    """A release uses Apple credentials when complete, or ad-hoc signing."""
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "Detect Apple release credentials" in workflow
    assert "APPLE_CERTIFICATE_P12_BASE64" in workflow
    assert "APPLE_CERTIFICATE_PASSWORD" in workflow
    assert "APPLE_SIGNING_IDENTITY" in workflow
    assert "APPLE_ID" in workflow
    assert "APPLE_TEAM_ID" in workflow
    assert "APPLE_APP_SPECIFIC_PASSWORD" in workflow
    assert 'codesign --force --sign "$APPLE_SIGNING_IDENTITY"' in workflow
    assert "--options runtime --timestamp" in workflow
    assert "Partial Apple credential set" in workflow
    assert workflow.count("steps.apple-creds.outputs.available == 'true'") >= 4
    assert "Ad-hoc sign macOS application without Apple credentials" in workflow
    assert "steps.apple-creds.outputs.available == 'false'" in workflow
    assert 'codesign --force --sign - --options runtime --timestamp=none "$app"' in workflow
    assert "OUVRIR-MACOS.md" in workflow
    assert 'mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"' in workflow
    assert 'Contents/Resources/models' in workflow
    assert 'Contents/Resources/config.toml' in workflow
    assert 'Contents/Resources/ObsidianVault' in workflow
    assert "Run macOS bundle runtime tests" in workflow
    assert "Verify macOS bundle data initialization" in workflow
    assert "--runtime-smoke" in workflow
    assert 'test -L "$test_data/models/$MODEL_FILE"' in workflow


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


def test_rust_macos_distribution_does_not_bypass_quarantine() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    launcher = (ROOT / "rust" / "scripts" / "run.sh").read_text(encoding="utf-8")
    self_test = (ROOT / "rust" / "scripts" / "self-test.sh").read_text(
        encoding="utf-8"
    )

    assert "PRIORIS.app/Contents/MacOS/prioris" in launcher
    assert "PRIORIS.app/Contents/MacOS/prioris" in self_test
    instructions = (ROOT / "rust" / "OUVRIR-MACOS.md").read_text(encoding="utf-8")

    for content in (workflow, launcher, self_test, instructions):
        assert "com.apple.quarantine" not in content
        assert "xattr -d" not in content
        assert "xattr -dr" not in content
    assert "Ouvrir quand même" in instructions
    assert "Open Anyway" in instructions
