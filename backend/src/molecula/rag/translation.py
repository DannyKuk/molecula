import openai
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from molecula import prompts
from molecula.rag.language import detect_language
from molecula.schemas.retrieval import (
    QueryTranslation,
    QueryTranslationMode,
    Rewrites,
    TranslationStep,
)
from molecula.schemas.usage import usage_of

MAX_REWRITES = 3


class QueryTranslator:
    """Writes the queries a label search runs for a question, as QUERY_TRANSLATION says (#446).

    "off" searches the question as written. "translate" searches a German question in English,
    as the chat model translates it; any other question is searched as written, without a model
    call. "multi_query" searches the question and up to three rewrites the chat model writes,
    which the retriever merges by reciprocal rank fusion. #114 measured both and left them off:
    translation found 3 more of 94 answering passages for ~4 s per search, rewrites 5 fewer.

    When the model fails or writes nothing usable, the question is searched as written and
    `QueryTranslation.error` says why.
    """

    def __init__(self, model: BaseChatModel, mode: QueryTranslationMode) -> None:
        self._model = model
        self._mode = mode

    def translate(self, question: str) -> QueryTranslation:
        if self._mode == "off":
            return QueryTranslation(queries=[question])
        if self._mode == "translate":
            if detect_language(question) != "de":
                return QueryTranslation(queries=[question])
            return translated(self._model, question)
        return rewritten(self._model, question)


def translated(model: BaseChatModel, question: str) -> QueryTranslation:
    # The question goes in its own message, never into the prompt: it is untrusted text.
    messages = [SystemMessage(prompts.load("rag/translate_query")), HumanMessage(question)]
    try:
        reply = model.invoke(messages)
    # What agent/llm.py calls ChatModelError; rag/ doesn't import the agent.
    except openai.APIError as error:
        return QueryTranslation(queries=[question], error=repr(error))
    usage = usage_of(reply)
    english = " ".join(reply.text.split())
    if not english:
        return QueryTranslation(
            queries=[question], error="the model returned no translation", usage=usage
        )
    return QueryTranslation(
        queries=[english],
        steps=[TranslationStep(step="translation", output=english)],
        usage=usage,
    )


def rewritten(model: BaseChatModel, question: str) -> QueryTranslation:
    structured = model.with_structured_output(Rewrites, include_raw=True)
    messages = [SystemMessage(prompts.load("rag/rewrite_query")), HumanMessage(question)]
    try:
        result = structured.invoke(messages)
    except openai.APIError as error:
        return QueryTranslation(queries=[question], error=repr(error))
    usage = usage_of(result["raw"])
    parsed = result["parsed"]
    if not isinstance(parsed, Rewrites):
        error = result["parsing_error"] or "the model returned no rewrites"
        return QueryTranslation(queries=[question], error=str(error), usage=usage)
    rewrites = [text for text in (" ".join(r.split()) for r in parsed.rewrites) if text]
    rewrites = list(dict.fromkeys(r for r in rewrites if r != question))[:MAX_REWRITES]
    return QueryTranslation(
        queries=[question, *rewrites],
        steps=[
            TranslationStep(step=f"rewrite {number}", output=rewrite)
            for number, rewrite in enumerate(rewrites, start=1)
        ],
        usage=usage,
    )
