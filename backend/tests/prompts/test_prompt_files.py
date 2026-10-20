"""Checks every prompt file under `molecula/prompts/`, so new prompts are covered as they land."""

import pytest

from fake_llm import CANARY
from molecula import prompts
from molecula.prompts import PromptLoader, PromptVariableError
from molecula.prompts.loader import PROMPTS_DIR


def test_every_prompt_file_has_a_valid_name_and_valid_placeholders() -> None:
    loader = PromptLoader()

    for name in loader.names():
        loader.template(name)


def test_the_system_prompt_needs_its_canary_and_has_it_on_the_first_line() -> None:
    with pytest.raises(PromptVariableError, match="canary"):
        prompts.load("agent/system")

    first_line = prompts.load("agent/system", canary=CANARY).splitlines()[0]

    assert CANARY in first_line


def test_a_template_keeps_the_prompt_as_written() -> None:
    template = prompts.template("agent/system")

    assert "{canary}" in template.text.splitlines()[0]
    assert template.text == (PROMPTS_DIR / "agent/system.md").read_text("utf-8")
