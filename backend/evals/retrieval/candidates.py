from dataclasses import dataclass

# From the BGE model card: v1.5 works without it, but it is recommended for short queries
# that retrieve passages.
BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


@dataclass(frozen=True)
class Candidate:
    """An embedding model and the prefixes its model card asks for. Prompts the model ships
    with (Qwen3's query instruction) are applied by sentence-transformers on top."""

    label: str
    model: str
    query_prefix: str = ""
    document_prefix: str = ""


CANDIDATES = [
    Candidate("bge-small", "BAAI/bge-small-en-v1.5"),
    Candidate("bge-small+instruction", "BAAI/bge-small-en-v1.5", BGE_QUERY_INSTRUCTION),
    Candidate("medembed-small", "abhinand/MedEmbed-small-v0.1"),
    Candidate("bge-large", "BAAI/bge-large-en-v1.5"),
    Candidate("bge-large+instruction", "BAAI/bge-large-en-v1.5", BGE_QUERY_INSTRUCTION),
    Candidate(
        "modernbert-embed",
        "nomic-ai/modernbert-embed-base",
        query_prefix="search_query: ",
        document_prefix="search_document: ",
    ),
    Candidate("qwen3-0.6b", "Qwen/Qwen3-Embedding-0.6B"),
]
