"""Checks every prompt file under `molecula/prompts/`, so new prompts are covered as they land."""

from molecula.prompts import PromptLoader


def test_every_prompt_file_has_a_valid_name_and_valid_placeholders() -> None:
    loader = PromptLoader()

    for name in loader.names():
        loader.template(name)
