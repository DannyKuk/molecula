import asyncio
import logging
import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

import pytest
from langchain_core.messages import ToolMessage

from fake_llm import ScriptedChatModel, tool_call_message
from molecula.agent.decisions import DecisionModelError, DecisionModelTimeout
from molecula.agent.label_filter import DecisionFirstFilterExtractor
from molecula.rag.filters import SECTION_GROUP_ORDER
from molecula.schemas.decisions import (
    DecisionResponse,
    DecisionUsage,
    NoulAnswer,
    Question,
    StateMessage,
)
from molecula.schemas.retrieval import LabelQuery
from molecula.services.compounds import CompoundService
from molecula.services.labels import LabelService
from molecula.store.compounds import CompoundStore, Synonym
from molecula.store.labels import LabelRecord, LabelSection, LabelStore
from molecula.store.structures import ConformerFiles
from molecula.tools.search_labels import search_labels_tool
from store_records import compound_record
from tool_fakes import FakeLabelRetriever

FETCHED_AT = datetime(2026, 10, 19, tzinfo=UTC)
QUESTION = "What are the side effects of Gleevec?"


class Decisions:
    """Says yes to adverse reactions only, or raises `error`; counts its calls."""

    def __init__(self, error: DecisionModelError | None = None) -> None:
        self.error = error
        self.calls = 0

    async def decide(
        self, state: str | list[StateMessage], questions: Mapping[str, Question]
    ) -> DecisionResponse:
        self.calls += 1
        if self.error is not None:
            raise self.error
        answers = {
            group: NoulAnswer(type="noul", noul=0.9 if group == "adverse_reactions" else 0.1)
            for group in SECTION_GROUP_ORDER
        }
        return DecisionResponse(
            model="typesafe/jev-1.13",
            answers=dict(answers),
            usage=DecisionUsage(input_tokens=1290, cost=0.00005),
        )


@pytest.fixture
def services(conn: sqlite3.Connection, tmp_path: Path) -> tuple[CompoundService, LabelService]:
    compounds = CompoundStore(conn)
    labels = LabelStore(conn)
    compounds.save(
        compound_record(5291, "imatinib"),
        [Synonym("imatinib", "name"), Synonym("Gleevec", "alias")],
        FETCHED_AT,
    )
    label = LabelRecord(
        set_id="gleevec",
        substance="IMATINIB MESYLATE",
        brand="Gleevec",
        product_type="rx",
        effective_time="20260101",
        url="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=gleevec",
        sections=(LabelSection("adverse_reactions", "adverse_reactions", "Nausea.", False),),
    )
    labels.save(5291, (label,), FETCHED_AT)
    return (
        CompoundService(compounds, ConformerFiles(tmp_path), suggestion_cutoff=0.8),
        LabelService(labels, compounds),
    )


def extractor(
    services: tuple[CompoundService, LabelService], decisions: Decisions
) -> tuple[DecisionFirstFilterExtractor, ScriptedChatModel]:
    chat_model = ScriptedChatModel(
        script=[
            tool_call_message(
                "LabelQuery",
                LabelQuery(substances=["Gleevec"], section_groups=["warnings"]).model_dump(),
            )
        ]
    )
    return DecisionFirstFilterExtractor(chat_model, decisions, *services), chat_model


def test_the_decision_model_fills_the_filter_without_the_chat_model(
    services: tuple[CompoundService, LabelService],
) -> None:
    filters, chat_model = extractor(services, Decisions())

    found = filters.extract(QUESTION)

    assert found.set_ids == ["gleevec"]
    assert found.section_groups == ["adverse_reactions"]
    assert found.extraction_usage is not None
    assert found.extraction_usage.cost_usd == 0.00005
    assert chat_model.received == []


def test_a_failed_decision_model_falls_back_to_the_chat_model(
    services: tuple[CompoundService, LabelService], caplog: pytest.LogCaptureFixture
) -> None:
    decisions = Decisions(DecisionModelTimeout("https://openrouter.ai/api/v1: timed out"))
    filters, chat_model = extractor(services, decisions)

    with caplog.at_level(logging.WARNING):
        found = filters.extract(QUESTION)

    assert decisions.calls == 1
    assert len(chat_model.received) == 1
    assert found.section_groups == ["warnings"]
    assert found.extraction_error is None
    assert "The chat model extracts the label filter" in caplog.text


def test_a_drug_the_agent_names_asks_neither_model(
    services: tuple[CompoundService, LabelService],
) -> None:
    decisions = Decisions()
    filters, chat_model = extractor(services, decisions)

    found = filters.filter_for(QUESTION, drug="Gleevec", section="adverse_reactions")

    assert found.set_ids == ["gleevec"]
    assert decisions.calls == 0
    assert chat_model.received == []


def test_the_search_tool_asks_the_decision_model_when_the_agent_runs_it(
    services: tuple[CompoundService, LabelService],
) -> None:
    decisions = Decisions()
    filters, _ = extractor(services, decisions)
    retriever = FakeLabelRetriever()
    tool = search_labels_tool(filters, retriever)
    call = {"type": "tool_call", "name": tool.name, "args": {"question": QUESTION}, "id": "1"}

    # The agent awaits its tools; a sync tool runs in a worker thread.
    message = asyncio.run(tool.ainvoke(call))

    assert isinstance(message, ToolMessage)
    assert decisions.calls == 1
    [searched] = retriever.searched
    assert searched is not None and searched.section_groups == ["adverse_reactions"]
