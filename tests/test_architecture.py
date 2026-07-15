"""Contrainte d'architecture (§1.4, §12.1) : core/ est pur.

core/ n'importe ni store/, ni bot/, ni vault/, ni SQLite, ni Telegram,
ni aucun client LLM/réseau. C'est une contrainte, pas une convention.
"""
import re
from pathlib import Path

CORE = Path(__file__).parent.parent / "prioris" / "core"

FORBIDDEN = [
    r"prioris\.store", r"prioris\.bot", r"prioris\.vault",
    r"\bsqlite3\b", r"\btelegram\b", r"\brequests\b", r"\bhttpx\b",
    r"\bopenai\b", r"\banthropic\b", r"\bollama\b", r"\burllib\b",
    r"\bsocket\b", r"\bsubprocess\b",
]


def test_core_est_pur():
    for py in CORE.glob("*.py"):
        source = py.read_text(encoding="utf-8")
        imports = [line for line in source.splitlines()
                   if re.match(r"\s*(import|from)\s", line)]
        for line in imports:
            for pattern in FORBIDDEN:
                assert not re.search(pattern, line), \
                    f"{py.name} : import interdit dans core/ → {line.strip()}"


def test_core_sans_io_fichier():
    for py in CORE.glob("*.py"):
        source = py.read_text(encoding="utf-8")
        assert not re.search(r"\bopen\(", source), \
            f"{py.name} : I/O fichier interdite dans core/"
