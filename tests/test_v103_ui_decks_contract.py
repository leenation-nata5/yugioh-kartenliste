from pathlib import Path
root = Path(__file__).resolve().parents[1]
text = (root / "main.py").read_text(encoding="utf-8")
assert "MAX_DECKS = 50" in text
assert "favorite_deck_entries" in text
assert "open_all_decks_popup" in text
assert "Scannen. Sammeln. Decks bauen." in text
assert "Clock.schedule_once(lambda *_: choose_live(), 0.12)" in text
print("test_v103_ui_decks_contract: OK")
