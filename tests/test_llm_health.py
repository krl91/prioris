from prioris.llm import health


class FakeFacade:
    def __init__(self, results):
        self.results = list(results)
        self.available = True
        self.last_error = ""
        self.calls = 0

    def warm_up(self):
        self.calls += 1
        ok = self.results.pop(0)
        self.last_error = "" if ok else "boom"
        return ok


def test_warmup_reussit_apres_retry(tmp_path):
    facade = FakeFacade([False, True])
    ok, msg, path = health.warm_up_with_retries(
        facade, attempts=3, log_path=tmp_path / "llm.log")
    assert ok is True
    assert "2/3" in msg
    assert facade.calls == 2
    assert path.read_text("utf-8").count("warmup tentative") == 2


def test_warmup_echec_cree_log(tmp_path):
    facade = FakeFacade([False, False, False])
    ok, msg, path = health.warm_up_with_retries(
        facade, attempts=3, log_path=tmp_path / "llm.log")
    assert ok is False
    assert "LLM KO" in msg
    text = path.read_text("utf-8")
    assert "boom" in text
    assert text.count("KO") == 3
