from pathlib import Path

import pytest

from molecula import prompts
from molecula.prompts import (
    PromptFormatError,
    PromptLoader,
    PromptNotFound,
    PromptVariableError,
)
from molecula.prompts.loader import PROMPTS_DIR


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "prompts"


def write(root: Path, name: str, text: str) -> None:
    path = root / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_loads_a_prompt_without_variables(root: Path) -> None:
    write(root, "agent/system", "You answer questions about medicines.\n")

    assert PromptLoader(root).load("agent/system") == "You answer questions about medicines.\n"


def test_fills_every_placeholder(root: Path) -> None:
    write(root, "agent/system", "Today is {today}. Answer about {drug}, and only {drug}.")

    text = PromptLoader(root).load("agent/system", today="2026-10-11", drug="imatinib")

    assert text == "Today is 2026-10-11. Answer about imatinib, and only imatinib."


def test_a_variable_called_name_is_allowed(root: Path) -> None:
    write(root, "greeting", "Hello {name}.")

    assert PromptLoader(root).load("greeting", name="Danny") == "Hello Danny."


def test_values_are_inserted_as_text_and_not_parsed_again(root: Path) -> None:
    write(root, "rag/answer", "Context:\n{context}")

    text = PromptLoader(root).load("rag/answer", context="Take {dose} with {{water}}")

    assert text == "Context:\nTake {dose} with {{water}}"


def test_doubled_braces_are_literal_braces(root: Path) -> None:
    write(root, "rag/query_translation", 'Reply with JSON: {{"queries": ["{question}"]}}')

    text = PromptLoader(root).load("rag/query_translation", question="what is imatinib")

    assert text == 'Reply with JSON: {"queries": ["what is imatinib"]}'


def test_missing_variable_names_the_prompt_and_the_variable(root: Path) -> None:
    write(root, "agent/system", "Today is {today}. The user is {user}.")

    with pytest.raises(PromptVariableError, match=r"'agent/system'.*missing.*'user'"):
        PromptLoader(root).load("agent/system", today="2026-10-11")


def test_unused_variable_names_the_prompt_and_the_variable(root: Path) -> None:
    write(root, "agent/system", "Today is {today}.")

    with pytest.raises(PromptVariableError, match=r"'agent/system'.*unused.*'tone'"):
        PromptLoader(root).load("agent/system", today="2026-10-11", tone="friendly")


def test_unknown_name_fails(root: Path) -> None:
    write(root, "agent/system", "Hi.")

    with pytest.raises(PromptNotFound, match="agent/missing"):
        PromptLoader(root).load("agent/missing")


def test_a_folder_is_not_a_prompt(root: Path) -> None:
    write(root, "agent/system", "Hi.")

    with pytest.raises(PromptNotFound):
        PromptLoader(root).load("agent")


@pytest.mark.parametrize(
    "name",
    [
        "../secret",
        "agent/../../secret",
        "/etc/passwd",
        "C:/secret",
        "agent\\system",
        "agent/system.md",
        "Agent/System",
        "agent//system",
        "",
    ],
)
def test_names_that_could_leave_the_folder_or_differ_by_platform_are_refused(
    root: Path, name: str
) -> None:
    write(root, "agent/system", "Hi.")
    (root.parent / "secret.md").write_text("outside", encoding="utf-8")

    with pytest.raises(PromptNotFound, match="not a prompt name"):
        PromptLoader(root).load(name)


@pytest.mark.parametrize(
    ("text", "bad"),
    [
        ('Reply with {"queries": []}', '{"queries": []}'),
        ("Item {0}", "{0}"),
        ("Empty {}", "{}"),
        ("Spaced { today }", "{ today }"),
        ("Attribute {drug.name}", "{drug.name}"),
        ("Index {drugs[0]}", "{drugs[0]}"),
        ("Conversion {drug!r}", "{drug!r}"),
        ("Format {mw:.2f}", "{mw:.2f}"),
    ],
)
def test_anything_but_a_plain_placeholder_in_braces_fails(root: Path, text: str, bad: str) -> None:
    write(root, "rag/answer", text)

    with pytest.raises(PromptFormatError) as error:
        PromptLoader(root).load("rag/answer")

    assert f"prompt 'rag/answer': bad placeholder {bad}" in str(error.value)


@pytest.mark.parametrize("text", ["Open { brace", "Close } brace", "JSON {{ half }"])
def test_an_unpaired_brace_fails(root: Path, text: str) -> None:
    write(root, "rag/answer", text)

    with pytest.raises(PromptFormatError, match=r"'rag/answer'.*literal braces"):
        PromptLoader(root).load("rag/answer")


def test_a_file_is_read_once(root: Path) -> None:
    write(root, "agent/system", "First {today}.")
    loader = PromptLoader(root)
    loader.load("agent/system", today="Monday")

    write(root, "agent/system", "Second {today}.")

    assert loader.load("agent/system", today="Tuesday") == "First Tuesday."
    assert PromptLoader(root).load("agent/system", today="Tuesday") == "Second Tuesday."


def test_names_lists_every_markdown_file(root: Path) -> None:
    write(root, "agent/system", "Hi.")
    write(root, "rag/query_translation", "Hi.")
    write(root, "Bad-Name", "Hi.")
    (root / "notes.txt").write_text("not a prompt", encoding="utf-8")

    assert PromptLoader(root).names() == ["Bad-Name", "agent/system", "rag/query_translation"]


def test_module_level_load_uses_the_default_loader(
    monkeypatch: pytest.MonkeyPatch, root: Path
) -> None:
    write(root, "agent/system", "Today is {today}.")
    monkeypatch.setattr(prompts.loader, "default_loader", PromptLoader(root))

    assert prompts.load("agent/system", today="Monday") == "Today is Monday."


def test_the_default_root_is_the_prompts_package_folder() -> None:
    assert PromptLoader().root == PROMPTS_DIR == Path(prompts.__file__).resolve().parent
