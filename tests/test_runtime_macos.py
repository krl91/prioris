"""Test the bundled macOS runtime signature and runtime search path.

These tests ensure that dyld can load the bundled llama-simple runtime on the
user's machine. They only run on macOS and skip when the binary is missing or
unsigned.

Covered regressions:
  - an absolute CI build rpath instead of @executable_path;
  - Hardened Runtime Team ID mismatch without disable-library-validation.
"""
from __future__ import annotations

import platform
import subprocess
from pathlib import Path

import pytest

_MACHINE = platform.machine().lower()
_RUNTIME_PLATFORM = "macos-x64" if _MACHINE in ("x86_64", "amd64") else "macos-arm64"
_RUNTIME_BIN = Path(__file__).parent.parent / "runtime" / _RUNTIME_PLATFORM / "llama-simple"


def _codesign_info(binary: Path) -> str:
    result = subprocess.run(
        ["codesign", "-dv", str(binary)],
        capture_output=True, text=True,
    )
    return result.stdout + result.stderr


@pytest.fixture(scope="module")
def signed_macos_runtime():
    if platform.system() != "Darwin":
        pytest.skip("macOS only")
    if not _RUNTIME_BIN.exists():
        pytest.skip(f"missing binary: {_RUNTIME_BIN}")
    info = _codesign_info(_RUNTIME_BIN)
    if "adhoc" not in info and "Signature" not in info:
        pytest.skip("unsigned binary (local build without codesign)")
    return _RUNTIME_BIN


def test_rpath_contains_executable_path(signed_macos_runtime):
    """The binary must include @executable_path in LC_RPATH.

    Otherwise dyld searches for libllama in the CI build directory, which does
    not exist on the user's machine.
    """
    result = subprocess.run(
        ["otool", "-l", str(signed_macos_runtime)],
        capture_output=True, text=True, check=True,
    )
    assert "@executable_path" in result.stdout, (
        "llama-simple n'a pas @executable_path dans son rpath.\n"
        "Fix : install_name_tool -add_rpath @executable_path llama-simple"
    )


def test_entitlement_disable_library_validation(signed_macos_runtime):
    """The runtime must include the disable-library-validation entitlement.

    Hardened Runtime requires loaded dylibs to use the main binary's Team ID.
    Ad-hoc signatures have no shared Team ID, so strict library validation
    rejects them unless this entitlement is present.
    """
    result = subprocess.run(
        ["codesign", "-dv", "--entitlements", "-", str(signed_macos_runtime)],
        capture_output=True, text=True,
    )
    output = result.stdout + result.stderr
    assert "disable-library-validation" in output, (
        "llama-simple manque l'entitlement "
        "com.apple.security.cs.disable-library-validation.\n"
        "Fix : codesign avec --options runtime "
        "--entitlements <plist contenant disable-library-validation>"
    )
