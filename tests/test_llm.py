"""Tests de la couche LLM (§12.1) — transport factice, AUCUN réseau.

Le contrat testé : jamais d'exception qui remonte, jamais de valeur
hors échelle acceptée, repli None systématique.
"""
import json

import pytest

from prioris.core.axes import Axis
from prioris.llm.client import ChatClient, LLMConfig, LLMError, resolve
from prioris.llm.facade import LLMFacade, _extract_json
from prioris.llm.shortlist import shortlist_tasks


# --------------------------------------------------------------- config
def test_presets_providers():
    assert resolve(LLMConfig(provider="prioris"))[0] == "builtin://prioris"
    assert resolve(LLMConfig(provider="local_gguf", runner_path="bin/llama-cli",
                             model="models/ministral.gguf"))[0] == "local://gguf"
    assert resolve(LLMConfig(provider="ollama"))[0] == "http://localhost:11434/v1"
    assert resolve(LLMConfig(provider="lmstudio"))[0] == "http://localhost:1234/v1"
    assert resolve(LLMConfig(provider="openai"))[0] == "https://api.openai.com/v1"
    assert resolve(LLMConfig(provider="anthropic"))[0] == "https://api.anthropic.com/v1"
    assert resolve(LLMConfig(provider="copilot"))[0] == "https://api.githubcopilot.com"


def test_timeouts_par_defaut():
    # Local long : chargement du modèle peut dépasser 1 min (terrain v0.2.2)
    assert resolve(LLMConfig(provider="prioris"))[1] == 0.0
    assert resolve(LLMConfig(provider="local_gguf", runner_path="bin/llama-cli",
                             model="models/ministral.gguf"))[1] == 120.0
    assert resolve(LLMConfig(provider="ollama"))[1] == 120.0
    assert resolve(LLMConfig(provider="openai"))[1] == 15.0
    assert resolve(LLMConfig(provider="anthropic"))[1] == 30.0
    assert resolve(LLMConfig(provider="copilot"))[1] == 30.0


def test_timeout_surchargeable():
    assert resolve(LLMConfig(provider="ollama", timeout_s=5))[1] == 5.0


def test_custom_base_url_prioritaire():
    cfg = LLMConfig(provider="custom", base_url="http://nas:8080/v1/")
    assert resolve(cfg)[0] == "http://nas:8080/v1"


def test_provider_inconnu_sans_base_url():
    with pytest.raises(ValueError):
        resolve(LLMConfig(provider="mystere"))


def test_local_gguf_exige_runner_si_auto_inconnu(monkeypatch):
    import prioris.llm.client as client_mod
    monkeypatch.setattr(client_mod.platform, "system", lambda: "Plan9")
    monkeypatch.setattr(client_mod.platform, "machine", lambda: "weird")
    with pytest.raises(ValueError):
        resolve(LLMConfig(provider="local_gguf", runner_path="auto",
                          model="models/m.gguf"))


def test_local_gguf_auto_resout_un_runtime(monkeypatch):
    import prioris.llm.client as client_mod
    monkeypatch.setattr(client_mod.platform, "system", lambda: "Windows")
    monkeypatch.setattr(client_mod.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(client_mod.os.path, "exists", lambda p: False)
    url, timeout = resolve(LLMConfig(provider="local_gguf", runner_path="auto",
                                     model="models/m.gguf"))
    assert url == "local://gguf"
    assert timeout == 120.0


def test_local_gguf_auto_utilise_llama_simple_macos(monkeypatch):
    import prioris.llm.client as client_mod
    monkeypatch.setattr(client_mod.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(client_mod.platform, "machine", lambda: "arm64")
    runner, model = client_mod._local_gguf_paths(
        LLMConfig(provider="local_gguf", runner_path="auto", model="m.gguf")
    )
    assert runner == "runtime/macos-arm64/llama-simple"
    assert model == "m.gguf"


def test_local_gguf_auto_utilise_llama_simple_windows(monkeypatch):
    import prioris.llm.client as client_mod
    monkeypatch.setattr(client_mod.platform, "system", lambda: "Windows")
    monkeypatch.setattr(client_mod.platform, "machine", lambda: "AMD64")
    runner, model = client_mod._local_gguf_paths(
        LLMConfig(provider="local_gguf", runner_path="auto", model="m.gguf")
    )
    assert runner == "runtime/windows-x64/llama-simple.exe"
    assert model == "m.gguf"


def test_local_gguf_auto_utilise_llama_simple_linux(monkeypatch):
    import prioris.llm.client as client_mod
    monkeypatch.setattr(client_mod.platform, "system", lambda: "Linux")
    monkeypatch.setattr(client_mod.platform, "machine", lambda: "x86_64")
    runner, model = client_mod._local_gguf_paths(
        LLMConfig(provider="local_gguf", runner_path="auto", model="m.gguf")
    )
    assert runner == "runtime/linux-x64/llama-simple"
    assert model == "m.gguf"


def test_local_gguf_retire_quarantaine_macos(monkeypatch, tmp_path):
    import prioris.llm.local_gguf as local_mod
    calls = []

    runner_dir = tmp_path / "runtime" / "macos-arm64"
    runner_dir.mkdir(parents=True)
    runner = runner_dir / "llama-simple"
    runner.write_text("#!/bin/sh\n", encoding="utf-8")

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        class Proc:
            returncode = 0
            stdout = ""
            stderr = ""
        return Proc()

    monkeypatch.setattr(local_mod.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(local_mod.subprocess, "run", fake_run)

    local_mod._clear_macos_quarantine(runner)

    assert calls == [(
        ["xattr", "-dr", "com.apple.quarantine", str(runner_dir)],
        {"check": False, "capture_output": True, "text": True, "timeout": 10},
    )]


def test_from_dict():
    cfg = LLMConfig.from_dict({"enabled": True, "provider": "LMStudio",
                               "model": "qwen"})
    assert cfg.enabled and cfg.provider == "lmstudio" and cfg.model == "qwen"


def test_from_dict_defaut_prioris():
    cfg = LLMConfig.from_dict({"enabled": True})
    assert cfg.provider == "prioris"
    assert cfg.model == "rules-v1"


def test_from_dict_local_gguf():
    cfg = LLMConfig.from_dict({
        "enabled": True,
        "provider": "local_gguf",
        "runner_path": "bin/llama-cli",
        "model": "models/ministral.gguf",
        "max_tokens": 128,
    })
    assert cfg.runner_path == "bin/llama-cli"
    assert cfg.model == "models/ministral.gguf"
    assert cfg.max_tokens == 128


# --------------------------------------------------------------- client
def fake_transport(content: str):
    def transport(url, payload, headers, timeout):
        transport.calls.append({"url": url, "payload": payload,
                                "headers": headers, "timeout": timeout})
        return {"choices": [{"message": {"content": content}}]}
    transport.calls = []
    return transport


def test_client_appelle_le_bon_endpoint():
    t = fake_transport("ok")
    client = ChatClient(LLMConfig(enabled=True, provider="ollama", model="m"), t)
    assert client.chat("sys", "usr") == "ok"
    call = t.calls[0]
    assert call["url"].endswith("/v1/chat/completions")
    assert call["payload"]["temperature"] == 0
    assert call["payload"]["model"] == "m"
    assert call["payload"]["max_tokens"] == 512


def test_client_applique_budget_par_appel_sans_depasser_config():
    t = fake_transport("ok")
    client = ChatClient(LLMConfig(enabled=True, provider="ollama", model="m",
                                  max_tokens=200), t)
    client.chat("sys", "usr", max_tokens=96)
    assert t.calls[0]["payload"]["max_tokens"] == 96


def test_client_api_key_en_header():
    t = fake_transport("ok")
    ChatClient(LLMConfig(enabled=True, provider="openai", model="m",
                         api_key="sk-x"), t).chat("s", "u")
    assert t.calls[0]["headers"]["Authorization"] == "Bearer sk-x"


def test_client_api_key_env_prioritaire(monkeypatch):
    t = fake_transport("ok")
    monkeypatch.setenv("PRIORIS_LLM_TOKEN", "env-token")
    ChatClient(LLMConfig(enabled=True, provider="openai", model="m",
                         api_key="file-token",
                         api_key_env="PRIORIS_LLM_TOKEN"), t).chat("s", "u")
    assert t.calls[0]["headers"]["Authorization"] == "Bearer env-token"


def test_client_copilot_headers():
    t = fake_transport("ok")
    ChatClient(LLMConfig(enabled=True, provider="copilot", model="gpt-4o",
                         api_key="ghu_x"), t).chat("s", "u")
    headers = t.calls[0]["headers"]
    assert headers["Authorization"] == "Bearer ghu_x"
    assert headers["Copilot-Integration-Id"] == "prioris-local-gui"


def test_client_anthropic_messages_endpoint():
    def transport(url, payload, headers, timeout):
        transport.calls.append({"url": url, "payload": payload,
                                "headers": headers, "timeout": timeout})
        return {"content": [{"type": "text", "text": '{"ok": true}'}]}
    transport.calls = []
    client = ChatClient(LLMConfig(enabled=True, provider="anthropic",
                                  model="claude-3-5-haiku-latest",
                                  api_key="sk-ant"), transport)
    assert json.loads(client.chat("sys", "usr"))["ok"] is True
    call = transport.calls[0]
    assert call["url"].endswith("/v1/messages")
    assert call["payload"]["system"] == "sys"
    assert call["headers"]["x-api-key"] == "sk-ant"
    assert call["headers"]["anthropic-version"] == "2023-06-01"


def test_client_prioris_interne_sans_transport():
    client = ChatClient(LLMConfig(enabled=True, provider="prioris", model="rules-v1"))
    raw = client.chat("Tu réponds uniquement en JSON.",
                      'Réponds exactement : {"ok": true}')
    assert json.loads(raw)["ok"] is True


def test_client_local_gguf_transport_injecte():
    def fake_local(cfg, system, user):
        assert cfg.runner_path == "bin/llama-cli"
        assert cfg.model_path == "models/ministral.gguf"
        assert cfg.max_tokens == 64
        return '{"ok": true}'

    client = ChatClient(
        LLMConfig(enabled=True, provider="local_gguf",
                  runner_path="bin/llama-cli",
                  model="models/ministral.gguf",
                  max_tokens=64),
        fake_local,
    )
    assert json.loads(client.chat("s", "u"))["ok"] is True


def test_local_gguf_nettoie_stdout_llamacpp():
    from prioris.llm.local_gguf import _clean_stdout
    raw = """Loading model...
> <|system|>
sys
<|assistant|>
```json
{"ok": true}
```
[ Prompt: 200 t/s | Generation: 20 t/s ]
Exiting...
"""
    assert json.loads(_clean_stdout(raw))["ok"] is True


def test_local_gguf_refuse_runtime_avec_serveur_local(monkeypatch, tmp_path):
    from prioris.llm.local_gguf import _assert_no_embedded_server
    import subprocess

    runner = tmp_path / "llama-cli"
    runner.write_text("")

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args[0],
            0,
            stdout="--server-base URL connect instead of starting a new one",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="serveur localhost"):
        _assert_no_embedded_server(runner)


def test_local_gguf_accepte_runtime_sans_serveur(monkeypatch, tmp_path):
    from prioris.llm.local_gguf import _assert_no_embedded_server
    import subprocess

    runner = tmp_path / "inference"
    runner.write_text("")

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout="pure cli", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    _assert_no_embedded_server(runner)


def test_local_gguf_appelle_llama_simple_sans_options_serveur(monkeypatch, tmp_path):
    from prioris.llm import local_gguf
    from prioris.llm.client_types import LocalGGUFConfig
    import subprocess

    runner = tmp_path / "llama-simple"
    model = tmp_path / "m.gguf"
    runner.write_text("")
    model.write_text("")

    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        if args[1:] == ["--help"]:
            return subprocess.CompletedProcess(args, 1, stdout="example usage: x -m model.gguf [-n n_predict]", stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="<|assistant|>\n{\"ok\": true}", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    raw = local_gguf.chat(LocalGGUFConfig(str(runner), str(model), 30, 16), "s", "u")
    assert json.loads(raw)["ok"] is True
    assert "--server-base" not in calls[-1]
    assert "--single-turn" not in calls[-1]
    assert calls[-1][:5] == [str(runner), "-m", str(model), "-n", "16"]


def test_facade_prioris_interprete_localement():
    cfg = LLMConfig(enabled=True, provider="prioris", model="rules-v1")
    f = LLMFacade(ChatClient(cfg))
    r = f.interpret_answer(Axis.BLK, "Qui est bloqué ?",
                           "Le client est bloqué si je ne le fais pas")
    assert r is not None
    assert r.valeur == 4
    assert r.incertitude == 0


def test_client_transport_en_panne():
    def broken(*a):
        raise ConnectionError("refusé")
    client = ChatClient(LLMConfig(enabled=True, provider="ollama", model="m"), broken)
    with pytest.raises(LLMError):
        client.chat("s", "u")


# --------------------------------------------------------------- façade
def facade_with(content_or_exc, cfg=None):
    cfg = cfg or LLMConfig(enabled=True, provider="ollama", model="test")
    if isinstance(content_or_exc, list):
        seq = iter(content_or_exc)

        def transport(url, payload, headers, timeout):
            item = next(seq)
            if isinstance(item, Exception):
                raise item
            return {"choices": [{"message": {"content": item}}]}
    else:
        def transport(url, payload, headers, timeout):
            if isinstance(content_or_exc, Exception):
                raise content_or_exc
            return {"choices": [{"message": {"content": content_or_exc}}]}
    return LLMFacade(ChatClient(cfg, transport))


VALID = json.dumps({"valeur": 2, "incertitude": 1,
                    "reformulation": "Tu penses qu'une personne est bloquée."})


def test_nlu_valide():
    r = facade_with(VALID).interpret_answer(Axis.BLK, "Qui est bloqué ?",
                                            "je crois que Marie attend")
    assert (r.valeur, r.incertitude) == (2, 1)
    assert r.axis == Axis.BLK and r.reformulation


def test_nlu_garde_assez_de_tokens_pour_fermer_le_json():
    transport = fake_transport(VALID)
    facade = LLMFacade(ChatClient(
        LLMConfig(enabled=True, provider="ollama", model="test"), transport))
    assert facade.interpret_answer(Axis.BLK, "Qui est bloqué ?", "Marie attend")
    assert transport.calls[0]["payload"]["max_tokens"] == 160


def test_nlu_json_dans_cloture_markdown():
    r = facade_with(f"```json\n{VALID}\n```").interpret_answer(
        Axis.BLK, "q", "texte")
    assert r is not None and r.valeur == 2


def test_question_nlu_valide_pour_priorite_subjective():
    raw = json.dumps({
        "value": "P2",
        "incertitude": 1,
        "reformulation": "Tu la vois importante mais pas urgente.",
    })
    r = facade_with(raw).interpret_question_answer(
        "Instinctivement, tu la classes comment ?",
        [("P1", "P1"), ("P2", "P2"), ("P3", "P3"), ("P4", "P4")],
        "plutôt important mais pas urgent",
    )
    assert r is not None
    assert (r.value, r.incertitude) == ("P2", 1)
    assert "importante" in r.reformulation


def test_question_nlu_rejette_option_inconnue():
    raw = json.dumps({
        "value": "P9",
        "incertitude": 0,
        "reformulation": "Tu choisis une option inexistante.",
    })
    assert facade_with(raw).interpret_question_answer(
        "q", [("P1", "P1")], "texte") is None


def test_valeur_hors_echelle_rejetee():
    bad = json.dumps({"valeur": 9, "incertitude": 0, "reformulation": "x"})
    assert facade_with(bad).interpret_answer(Axis.BLK, "q", "t") is None


def test_valeur_non_entiere_rejetee():
    for v in ["2", 2.5, True, None]:
        bad = json.dumps({"valeur": v, "incertitude": 0, "reformulation": "x"})
        assert facade_with(bad).interpret_answer(Axis.BLK, "q", "t") is None


def test_retry_puis_succes():
    r = facade_with(["pas du json", VALID]).interpret_answer(Axis.BLK, "q", "t")
    assert r is not None and r.valeur == 2


def test_deux_echecs_egale_repli():
    assert facade_with(["x", "y"]).interpret_answer(Axis.BLK, "q", "t") is None


def test_panne_totale_egale_repli_sans_exception():
    assert facade_with(ConnectionError("down")).interpret_answer(
        Axis.BLK, "q", "t") is None


def test_facade_sans_client_indisponible():
    f = LLMFacade(None)
    assert not f.available
    assert f.interpret_answer(Axis.BLK, "q", "t") is None


def test_facade_disabled_indisponible():
    cfg = LLMConfig(enabled=False, provider="ollama", model="m")
    f = LLMFacade(ChatClient(cfg, fake_transport(VALID)))
    assert not f.available


def test_journalisation_des_appels():
    calls = []
    cfg = LLMConfig(enabled=True, provider="ollama", model="m")
    f = LLMFacade(ChatClient(cfg, fake_transport(VALID)),
                  log_fn=lambda t, m, ms, ok: calls.append((t, m, ok)))
    f.interpret_answer(Axis.BLK, "q", "t")
    assert calls == [("nlu", "m", True)]


def test_revision_tache_valide_et_journalisee():
    calls = []
    raw = json.dumps({
        "changes": [{"axis": "BLK", "value": 4,
                     "reason": "Le client est maintenant bloqué."}],
        "explanation": "Je propose d'augmenter le blocage réel.",
    })
    f = LLMFacade(
        ChatClient(LLMConfig(enabled=True, provider="ollama", model="m"),
                   fake_transport(raw)),
        log_fn=lambda t, m, ms, ok: calls.append((t, m, ok)),
    )
    ctx = {
        "task": {"id": 1, "titre": "Test"},
        "evaluation": {"axes": {"BLK": {"valeur": 2, "max": 5}}},
    }
    result = f.revise_task(ctx, "Le client est bloqué.")
    assert result["changes"][0]["axis"] == "BLK"
    assert result["changes"][0]["value"] == 4
    assert calls == [("task_revision", "m", True)]


def test_revision_tache_rejette_axe_inconnu():
    raw = json.dumps({
        "changes": [{"axis": "BAD", "value": 4, "reason": "x"}],
        "explanation": "x",
    })
    f = facade_with(raw)
    ctx = {
        "task": {"id": 1, "titre": "Test"},
        "evaluation": {"axes": {"BLK": {"valeur": 2, "max": 5}}},
    }
    assert f.revise_task(ctx, "x") is None


def test_impact_taches_valide_et_journalise():
    calls = []
    raw = json.dumps({
        "impacted": [{"id": 2, "impact": "Le client bloque cette tâche."}],
        "new_task_title": "",
        "suggested_deadline": "2026-07-20",
        "direct_answer": "Oui, la tâche #2 est concernée.",
        "explanation": "Une tâche existante est concernée.",
    })
    f = LLMFacade(
        ChatClient(LLMConfig(enabled=True, provider="ollama", model="m"),
                   fake_transport(raw)),
        log_fn=lambda t, m, ms, ok: calls.append((t, m, ok)),
    )
    result = f.impacted_tasks([(1, "A"), (2, "Retour client")],
                              "Le client est bloqué")
    assert result["impacted"] == [{"id": 2, "impact": "Le client bloque cette tâche."}]
    assert result["direct_answer"] == "Oui, la tâche #2 est concernée."
    assert result["new_task_title"] == ""
    assert result["suggested_deadline"] == "2026-07-20"
    assert calls == [("task_impact", "m", True)]


def test_info_preslectionne_au_plus_cinq_taches_pertinentes():
    tasks = [(1, "Retour client"), (2, "Acheter du pain"),
             (3, "Préparer la réunion client"), (4, "Faire du sport")]
    assert shortlist_tasks(tasks, "Le client attend une réponse") == [
        (1, "Retour client"), (3, "Préparer la réunion client")]


def test_info_ne_transmet_que_la_presselection_au_llm():
    raw = json.dumps({
        "impacted": [{"id": 2, "impact": "Même sujet."}],
        "new_task_title": "", "suggested_deadline": "",
        "direct_answer": "", "explanation": "Lien clair.",
    })
    transport = fake_transport(raw)
    facade = LLMFacade(ChatClient(
        LLMConfig(enabled=True, provider="ollama", model="m"), transport))
    result = facade.impacted_tasks(
        [(1, "Retour client"), (2, "Acheter des pommes")],
        "Il faut acheter une pomme ce soir")
    sent = json.loads(transport.calls[0]["payload"]["messages"][1]["content"])
    assert sent["taches_existantes"] == [{"id": 2, "titre": "Acheter des pommes"}]
    assert result["impacted"][0]["id"] == 2


def test_abstention_ou_confiance_faible_declenche_repli_manuel():
    abstain = json.dumps({
        "valeur": 2, "incertitude": 2, "reformulation": "Je ne sais pas.",
        "status": "abstain", "confidence": 0.1,
    })
    facade = facade_with(abstain)
    assert facade.interpret_answer(Axis.IMP, "Impact ?", "je ne sais pas") is None
    assert "abstient" in facade.last_error


def test_impact_taches_ignore_date_invalide():
    raw = json.dumps({
        "impacted": [],
        "new_task_title": "Préparer le dossier",
        "suggested_deadline": "vendredi",
        "direct_answer": "",
        "explanation": "Nouvelle tâche proposée.",
    })
    f = facade_with(raw)
    result = f.impacted_tasks([(1, "A")], "Préparer le dossier vendredi")
    assert result["suggested_deadline"] == ""


def test_impact_taches_rejette_id_inconnu():
    raw = json.dumps({
        "impacted": [{"id": 99, "impact": "x"}],
        "new_task_title": "",
        "direct_answer": "",
        "explanation": "x",
    })
    f = facade_with(raw)
    assert f.impacted_tasks([(1, "A")], "x") is None


def test_impact_taches_ignore_id_null_et_propose_nouvelle_tache():
    raw = json.dumps({
        "impacted": [{"id": None, "impact": ""}],
        "new_task_title": "toto doit manger une pomme d'ici une heure",
        "direct_answer": "",
        "explanation": "Aucune tâche existante ne semble concernée.",
    })
    f = facade_with(raw)
    result = f.impacted_tasks([(1, "Retour client")],
                              "toto doit manger une pomme d'ici une heure")
    assert result["impacted"] == []
    assert "pomme" in result["new_task_title"]


def test_subjective_challenge_questions_valide_et_journalise():
    calls = []
    raw = json.dumps({
        "questions": [
            "Quelle vraie échéance justifie P1 ?",
            "Est-ce une pression visible ou un impact réel ?",
            "Quel fait te ferait changer d'avis ?",
        ],
    })
    f = LLMFacade(
        ChatClient(LLMConfig(enabled=True, provider="ollama", model="m"),
                   fake_transport(raw)),
        log_fn=lambda t, m, ms, ok: calls.append((t, m, ok)),
    )
    questions = f.subjective_challenge_questions("Répondre au client", "P1")
    assert questions == [
        "Quelle vraie échéance justifie P1 ?",
        "Est-ce une pression visible ou un impact réel ?",
        "Quel fait te ferait changer d'avis ?",
    ]
    assert calls == [("subjective_challenge", "m", True)]


def test_subjective_challenge_prioris_local():
    cfg = LLMConfig(enabled=True, provider="prioris", model="rules-v1")
    f = LLMFacade(ChatClient(cfg))
    questions = f.subjective_challenge_questions("Répondre au client", "P1")
    assert questions is not None
    assert len(questions) == 3
    assert any("pression" in q.lower() for q in questions)


def test_interpret_challenge_answer_valide_et_journalise():
    calls = []
    raw = json.dumps({
        "axis": "CDR",
        "value": 3,
        "uncertainty": 0,
        "reason": "Une échéance réelle est mentionnée.",
    })
    f = LLMFacade(
        ChatClient(LLMConfig(enabled=True, provider="ollama", model="m"),
                   fake_transport(raw)),
        log_fn=lambda t, m, ms, ok: calls.append((t, m, ok)),
    )
    parsed = f.interpret_challenge_answer(
        "Répondre au client", "P1", "Quelle échéance ?", "demain", {"CDR": 0})
    assert parsed == {
        "axis": "CDR",
        "value": 3,
        "uncertainty": 0,
        "reason": "Une échéance réelle est mentionnée.",
    }
    assert calls == [("challenge_answer", "m", True)]


def test_interpret_challenge_answer_prioris_local():
    cfg = LLMConfig(enabled=True, provider="prioris", model="rules-v1")
    f = LLMFacade(ChatClient(cfg))
    parsed = f.interpret_challenge_answer(
        "Répondre au client", "P1", "Quelle échéance ?", "deadline demain", {})
    assert parsed is not None
    assert parsed["axis"] == "CDR"
    assert parsed["value"] == 3


def test_extract_json_texte_parasite():
    assert _extract_json(f"Voici :\n{VALID}\nvoilà.")["valeur"] == 2
    with pytest.raises(ValueError):
        _extract_json("aucun objet ici")


# ---------------------------------------------------- diagnostic (v0.2.1)
def test_last_error_explique_l_echec():
    f = facade_with(ConnectionError("connexion refusée"))
    assert f.interpret_answer(Axis.BLK, "q", "t") is None
    assert "refusée" in f.last_error
    f2 = facade_with(VALID)
    f2.interpret_answer(Axis.BLK, "q", "t")
    assert f2.last_error is None          # succès ⇒ erreur effacée


def test_self_test_ok():
    ok, msg = facade_with('{"ok": true}').self_test()
    assert ok and "OK" in msg and "ms" in msg


def test_self_test_panne_avec_indice():
    ok, msg = facade_with(TimeoutError("timed out")).self_test()
    assert not ok and "timeout" in msg.lower()
    ok, msg = facade_with(ConnectionError("connection refused")).self_test()
    assert not ok and "serveur" in msg


def test_warm_up():
    calls = []
    cfg = LLMConfig(enabled=True, provider="ollama", model="m")
    f = LLMFacade(ChatClient(cfg, fake_transport('{"pong": true}')),
                  log_fn=lambda t, m, ms, ok: calls.append((t, ok)))
    assert f.warm_up() is True
    assert calls == [("warmup", True)]


def test_warm_up_panne_silencieuse():
    f = facade_with(ConnectionError("down"))
    assert f.warm_up() is False        # jamais d'exception


def test_warm_up_indisponible():
    assert LLMFacade(None).warm_up() is False


def test_log_fn_defaillant_ne_tombe_jamais():
    """Régression v0.2.3 : une erreur de journalisation (ex. SQLite
    inter-threads) ne doit jamais faire tomber la façade."""
    def bad_log(*a):
        raise RuntimeError("log cassé")
    cfg = LLMConfig(enabled=True, provider="ollama", model="m")
    f = LLMFacade(ChatClient(cfg, fake_transport(VALID)), log_fn=bad_log)
    assert f.interpret_answer(Axis.BLK, "q", "t") is not None
    assert f.warm_up() is True
    ok, _ = f.self_test()   # VALID n'a pas de clé "ok" → joignable quand même
    assert ok


def test_log_llm_call_depuis_un_thread(tmp_path):
    """Régression v0.2.3 : écriture llm_calls depuis un thread de travail."""
    import threading
    from prioris.store import db as store_db
    conn = store_db.connect(tmp_path / "t.db")
    errors = []

    def worker():
        try:
            for _ in range(20):
                store_db.log_llm_call(conn, "nlu", "m", 10, True)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    n = conn.execute("SELECT COUNT(*) c FROM llm_calls").fetchone()["c"]
    assert n == 80


def test_self_test_desactive():
    cfg = LLMConfig(enabled=False, provider="ollama", model="m")
    ok, msg = LLMFacade(ChatClient(cfg, fake_transport('{"ok":true}'))).self_test()
    assert not ok and "désactivé" in msg
    ok, msg = LLMFacade(None).self_test()
    assert not ok
