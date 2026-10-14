from types import SimpleNamespace as NS

from noshow.bot import is_owner


def update(user_id, chat_type="private"):
    return NS(effective_user=NS(id=user_id), effective_chat=NS(id=999, type=chat_type))


def test_only_the_pinned_owner_in_a_private_chat_is_the_owner(monkeypatch):
    monkeypatch.setenv("TELEGRAM_OWNER_ID", "42")
    assert is_owner(update(42))
    assert not is_owner(update(7))
    assert not is_owner(update(42, chat_type="group"))


def test_nobody_is_owner_until_one_is_pinned(monkeypatch):
    monkeypatch.delenv("TELEGRAM_OWNER_ID", raising=False)
    assert not is_owner(update(42))
