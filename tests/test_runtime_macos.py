"""Tests de la signature et du rpath du runtime macOS.

Ces tests vérifient que llama-simple livré dans la release peut être
chargé par dyld sur la machine de l'utilisateur. Ils ne s'exécutent que
sur macOS et skippent silencieusement si le binaire est absent ou non signé.

Deux régressions couvertes :
  - rpath absolu CI (build/bin/) → @executable_path manquant
  - Hardened Runtime + Team ID mismatch → disable-library-validation manquant
"""
from __future__ import annotations

import platform
import subprocess
from pathlib import Path

import pytest

# Chemin attendu dans le bundle extrait (relatif à tests/)
_RUNTIME_BIN = Path(__file__).parent.parent / "runtime" / "macos-arm64" / "llama-simple"


def _codesign_info(binary: Path) -> str:
    result = subprocess.run(
        ["codesign", "-dv", str(binary)],
        capture_output=True, text=True,
    )
    return result.stdout + result.stderr


@pytest.fixture(scope="module")
def signed_macos_runtime():
    if platform.system() != "Darwin":
        pytest.skip("macOS uniquement")
    if not _RUNTIME_BIN.exists():
        pytest.skip(f"binaire absent : {_RUNTIME_BIN}")
    info = _codesign_info(_RUNTIME_BIN)
    if "adhoc" not in info and "Signature" not in info:
        pytest.skip("binaire non signé (build local sans codesign)")
    return _RUNTIME_BIN


def test_rpath_contains_executable_path(signed_macos_runtime):
    """@executable_path doit figurer dans le LC_RPATH du binaire.

    Sans ce rpath, dyld cherche libllama.0.dylib dans le répertoire de build
    du runner CI (/Users/runner/work/…) introuvable sur la machine de
    l'utilisateur.
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
    """L'entitlement disable-library-validation doit être présent.

    Avec Hardened Runtime, macOS vérifie que les dylibs chargées ont le même
    Team ID que le binaire principal. Avec la signature ad-hoc (Team ID = null),
    chaque binaire a sa propre identité et la validation échoue avec :
      «not valid for use in process: different Team IDs»
    L'entitlement com.apple.security.cs.disable-library-validation désactive
    cette vérification tout en conservant les autres protections.
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
