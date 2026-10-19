from collections import Counter

from evals.safety.dataset import InputCheckItem
from evals.safety.repeat import Sorts, report

from molecula.schemas.guard import InputCategory


def item(item_id: str, category: InputCategory, language: str = "en") -> InputCheckItem:
    return InputCheckItem.model_validate(
        {
            "id": item_id,
            "text": f"Message {item_id}",
            "language": language,
            "category": category,
            "source": "written for #286",
            "split": "test",
        }
    )


def sorts(seconds: float, **categories: int) -> Sorts:
    return Sorts(Counter(categories), [seconds] * sum(categories.values()))


ITEMS = [
    item("ok-en", "ok"),
    item("ok-de", "ok", "de"),
    item("lethal-en", "lethal_dose"),
]
RESULTS = {
    "ok-en": sorts(1.0, ok=2, personal_medical_advice=1),
    "ok-de": sorts(2.0, ok=3),
    "lethal-en": sorts(3.0, lethal_dose=3),
}


def test_the_report_counts_sorts_per_category_and_language() -> None:
    text = report(ITEMS, RESULTS, 3)

    assert "3 messages, 3 sorts per message" in text
    assert "| `ok` | 2/3 | 3/3 |" in text
    assert "| `lethal_dose` | 3/3 | - |" in text
    assert "False alarms (`ok` sorted as something else): 1 of 6 sorts" in text
    assert "Missed (unsafe sorted as `ok`): 0 of 3 sorts" in text
    assert "Seconds per sort: p50 2.00, max 3.00" in text


def test_the_report_lists_only_the_messages_not_always_sorted_right() -> None:
    text = report(ITEMS, RESULTS, 3)

    assert "| ok-en | ok | 2 | personal_medical_advice 1 |" in text
    assert "| ok-de |" not in text
    assert "| lethal-en |" not in text
