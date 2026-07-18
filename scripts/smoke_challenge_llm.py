#!/usr/bin/env python3
"""Exercise a bundled LLM on the non-blocking false-premise workflow."""
from __future__ import annotations

import pathlib
import sys
import tomllib

REPOSITORY_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from prioris.llm.client import ChatClient, LLMConfig
from prioris.llm.facade import LLMFacade


def main() -> int:
    config_path = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "config.toml")
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    facade = LLMFacade(ChatClient(LLMConfig.from_dict(config["llm"])))
    result = facade.interpret_challenge_answer(
        "Manger",
        "P1",
        "Pourquoi aucune action immédiate n'est-elle nécessaire ?",
        "La question comporte une information fausse.",
        {"BLK": 0, "CDR": 0, "HOR": 0, "IMP": 1,
         "INA": 0, "IRR": 0, "ALN": 0},
    )
    if result is None:
        raise RuntimeError(f"LLM challenge smoke test failed: {facade.last_error}")
    if result["outcome"] != "premise_false" or result["axis"] is not None:
        raise RuntimeError(f"unexpected challenge interpretation: {result}")
    binary = facade.interpret_challenge_answer(
        "Manager", "P1", "Y a-t-il une pression sociale ?", "non", {})
    if (binary is None or binary["axis"] is not None
            or binary["uncertainty"] != 0):
        raise RuntimeError(f"unexpected binary interpretation: {binary}")
    mirror = facade.interpret_question_answer(
        "Si tu attendais une semaine, que se passerait-il ?",
        [("Un vrai problème", "0"), ("Rien de grave, en fait", "1"),
         ("Je ne sais pas", "2")],
        "je meurt car j'ai besoin de manger pour vivre",
    )
    if mirror is None or mirror.value != "0" or mirror.incertitude != 0:
        raise RuntimeError(f"unexpected mirror interpretation: {mirror}")
    print("PRIORIS Python LLM: false premise, short 'no' and mirror accepted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
