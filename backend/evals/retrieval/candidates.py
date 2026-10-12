from dataclasses import dataclass

# From the BGE model card: v1.5 works without it, but it is recommended for short queries
# that retrieve passages.
BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "
# The query prompt Qwen3-Embedding ships for sentence-transformers. OpenRouter's endpoint doesn't
# add it, so the cloud run prepends it as the local run does.
QWEN3_QUERY_INSTRUCTION = (
    "Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery:"
)


@dataclass(frozen=True)
class Candidate:
    """An embedding model and the prefixes its model card asks for. Prompts a local model ships
    with (Qwen3's query instruction) are applied by sentence-transformers on top. A cloud model
    is called through OpenRouter."""

    label: str
    model: str
    query_prefix: str = ""
    document_prefix: str = ""
    cloud: bool = False


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
    Candidate("bge-m3", "BAAI/bge-m3"),
    Candidate("qwen3-0.6b", "Qwen/Qwen3-Embedding-0.6B"),
    Candidate("qwen3-4b", "Qwen/Qwen3-Embedding-4B"),
    Candidate("qwen3-8b", "Qwen/Qwen3-Embedding-8B"),
    Candidate("cloud:text-embedding-3-small", "openai/text-embedding-3-small", cloud=True),
    Candidate("cloud:text-embedding-3-large", "openai/text-embedding-3-large", cloud=True),
    Candidate("cloud:gemini-embedding-2", "google/gemini-embedding-2", cloud=True),
    Candidate("cloud:qwen3-8b", "qwen/qwen3-embedding-8b", QWEN3_QUERY_INSTRUCTION, cloud=True),
]
