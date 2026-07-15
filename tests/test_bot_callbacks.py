import asyncio

from prioris.bot import handlers
from prioris.store import db


class FakeMessage:
    chat_id = 123

    def __init__(self):
        self.replies = []

    async def reply_text(self, text, reply_markup=None):
        self.replies.append({"text": text, "reply_markup": reply_markup})
        return self

    async def reply_photo(self, photo, caption=None, reply_markup=None):
        self.replies.append({
            "photo": photo,
            "text": caption,
            "reply_markup": reply_markup,
        })
        return self


class FakeQuery:
    def __init__(self, data, message):
        self.data = data
        self.message = message
        self.answered = False

    async def answer(self):
        self.answered = True


class FakeUpdate:
    def __init__(self, query):
        self.callback_query = query


class FakeContext:
    def __init__(self, conn):
        self.bot_data = {"conn": conn}
        self.chat_data = {}


def _run_callback(data, context, message=None):
    message = message or FakeMessage()
    query = FakeQuery(data, message)
    asyncio.run(handlers.on_callback(FakeUpdate(query), context))
    return message, query


def test_telegram_cat_propose_confirmation_date_llm(tmp_path):
    conn = db.connect(tmp_path / "prioris.db")
    context = FakeContext(conn)
    context.chat_data["pending_title"] = "toto doit manger une pomme"
    context.chat_data["pending_deadline_suggestion"] = "2026-07-15"

    message, query = _run_callback("cat|perso", context)

    assert query.answered is True
    assert context.chat_data["pending_task_meta"] == {
        "titre": "toto doit manger une pomme",
        "cat": "perso",
        "suggested_deadline": "2026-07-15",
    }
    reply = message.replies[-1]
    assert "Date détectée par le LLM : 2026-07-15" in reply["text"]
    callbacks = [
        button.callback_data
        for row in reply["reply_markup"].inline_keyboard
        for button in row
    ]
    assert callbacks == ["ddl|suggest", "ddl|ask", "ddl|none"]


def test_telegram_ddl_suggest_cree_tache_avec_deadline(tmp_path):
    conn = db.connect(tmp_path / "prioris.db")
    context = FakeContext(conn)
    context.chat_data["pending_title"] = "toto doit manger une pomme"
    context.chat_data["pending_deadline_suggestion"] = "2026-07-15"
    context.chat_data["pending_task_meta"] = {
        "titre": "toto doit manger une pomme",
        "cat": "perso",
        "suggested_deadline": "2026-07-15",
    }

    try:
        message, _ = _run_callback("ddl|suggest", context)

        row = conn.execute(
            "SELECT t.titre, c.code AS cat_code, t.deadline_reelle "
            "FROM tasks t LEFT JOIN categories c ON c.id = t.category_id"
        ).fetchone()
        assert row["titre"] == "toto doit manger une pomme"
        assert row["cat_code"] == "perso"
        assert row["deadline_reelle"] == "2026-07-15"
        assert "pending_title" not in context.chat_data
        assert "pending_deadline_suggestion" not in context.chat_data
        assert message.replies
    finally:
        handlers.SESSIONS.pop(FakeMessage.chat_id, None)
