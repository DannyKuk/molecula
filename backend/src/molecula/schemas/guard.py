from typing import Literal

from pydantic import BaseModel, ConfigDict

type InputCategory = Literal[
    "ok",
    "overdose_emergency",
    "personal_medical_advice",
    "lethal_dose",
    "synthesis_or_misuse",
    "prompt_injection",
    "off_topic",
]

type Language = Literal["en", "de"]


class SortedMessage(BaseModel):
    # No docstring: pydantic would send it to the model as the schema's description, and the
    # instructions for this field live in prompts/guard/classify.md.
    model_config = ConfigDict(frozen=True)

    category: InputCategory
