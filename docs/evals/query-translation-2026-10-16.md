# Query translation and multi-query, 2026-10-16

> **Answer:** Neither was worth building on 2026-10-16. Translating a German question to English finds the answering label passage for 3 more of 94 questions (recall@5 0.80 → 0.83, English 0.85), at about 4 s of gpt-oss-20b per search. Multi-query (the question plus 3 rewrites, merged) loses more questions than it gains (0.85 → 0.80). Asking the agent to write its search question in English costs nothing, but gpt-oss-20b still wrote 6 of 16 searches in German.
>
> Since #446 both steps are built as the setting `QUERY_TRANSLATION` (`off`, `translate`, `multi_query`), off by default for the reasons measured here ([label search](../design/search.md)).

#114 asked whether two query-translation steps make the label search find the answer more often, and to build a step only if a measurement shows it helps. Name recognition, the third step of #14, is built in the filter (#113). The baseline is `main` at 74aebb0.

## Setup

- **Questions:** the 94 retrieval questions (`backend/evals/datasets/retrieval_questions.yaml`) and a German version of each (`retrieval_questions_de.yaml`, written for #114), scored with the same answer key: the question's drug and one of its answering passages. Brand names stay as in English; generic names take their German spelling (Omeprazol), and acetaminophen is Paracetamol.
- **Search:** `LabelRetriever` on the built bge-m3 index, top 10, no score threshold, over the whole index and filtered to the question's drug. The drug filter is how the agent searches a question about one drug (it sets `drug`), so it is the row that counts.
- **Model:** `openai/gpt-oss-20b` in LM Studio, 32,768 tokens of context, one slot. It translated each German question (`prompts/rag/translate_query.md`) and wrote 3 rewrites of each English and each German question (`prompts/rag/rewrite_query.md`), one sample each. The rewrites were searched with the question and merged with reciprocal rank fusion (k = 60), each passage once.
- **Through the chat:** every fifth German question (19) asked through `POST /chat` in-process, guard included, to see in which language the agent writes the `question` of its `search_labels` calls and whether a search returns an answering passage in its first five (`python -m evals.chat_model.search_language`).

## Result

recall@k: the share of questions whose first answering passage is in the top k. MRR@10: the mean of 1 / its rank.

| Search question | Search | recall@1 | recall@5 | MRR@10 |
|---|---|---|---|---|
| English | whole index | 0.45 | 0.74 | 0.576 |
| German as written | whole index | 0.44 | 0.70 | 0.541 |
| German translated | whole index | 0.46 | 0.72 | 0.578 |
| English + 3 rewrites | whole index | 0.43 | 0.76 | 0.565 |
| German + 3 rewrites | whole index | 0.40 | 0.72 | 0.534 |
| English | drug | 0.50 | **0.85** | 0.643 |
| German as written | drug | 0.50 | **0.80** | 0.626 |
| German translated | drug | 0.53 | **0.83** | 0.661 |
| English + 3 rewrites | drug | 0.52 | 0.80 | 0.651 |
| German + 3 rewrites | drug | 0.50 | 0.81 | 0.628 |

Model time per question, median: translation 4.1 s, 3 rewrites 3.7 s.

Through the chat, 19 German questions:

| Tool description | Searches in German | Questions with an answering passage in a top 5 | No search (guard refused) |
|---|---|---|---|
| main | 8 of 16 | 12 of 19 | 3 |
| `search_labels` asks for the `question` in English | 6 of 16 | 14 of 19 | 3 |

## What it shows

- **German costs a little, and translation wins back most of it.** Filtered to the drug, a German question finds the passage for 5 fewer questions than its English original. Translated, it gains 4 (atorvastatin's starting dose, Ozempic's heart rate, Coreg and insulin, Singulair and aspirin asthma) and loses 1 (MS Contin in cirrhosis). bge-m3 is multilingual, which is why the gap is small to begin with.
- **The agent often translates already.** On main, gpt-oss-20b wrote half its searches in English for German questions. A translation step would run on that question, after the agent, so its gain in the app is smaller than in the table.
- **Multi-query loses.** Filtered to the drug, English with rewrites gains 2 questions and loses 7; German with rewrites gains 4 and loses 3. The fused list moves passages that a plain search ranked 2nd to 5th down to 6th or 7th.
- **The rewrites bring the model's memory into the search.** 150 of 563 rewrites are statements, not questions, and many state the answer: "Ibuprofen reduziert Schmerzen und Fieber durch Hemmung der Prostaglandinsynthese", "Proscar is indicated for … benign prostatic hyperplasia". The search then looks for what the model believes. 50 of the 282 rewrites of German questions stayed German though the prompt asks for English.
- **Asking for English in the tool description barely changes gpt-oss-20b.** Searches in German went from 8 to 6 of 16; the 2 more questions found are within one sample's spread (the guard refused a different question in each run, and "Does Nexium 24HR contain sugar?" was searched in English both times but found the passage only the second time). Kept, it would be a prompt change with a safety eval for no measured gain, so it is not on `main`.
- **The guard refuses some general German questions as personal advice:** "Darf jemand mit einer Sulfonamid-Allergie Acetazolamid nehmen?" and "Wann sollte ich Aleve absetzen…?" got the fixed answer in both runs, "Kann man Delsym bei Husten nehmen…?" and "Wann muss Gleevec wegen niedriger Blutwerte pausiert werden?" in one. That is #169, not the search.

## Tried and not built

| Step | Gain, drug filter | Cost | Why not built |
|---|---|---|---|
| Translate a non-English question to English | +3 of 94 (0.80 → 0.83) | one model call, ~4 s per search | The gain is 3 questions from one sample, the agent already writes half its searches in English, and the answer takes 7 to 12 s already |
| Multi-query: 3 rewrites, reciprocal rank fusion | −5 of 94 (0.85 → 0.80) | one model call and 3 more searches | It ranks the answering passage lower more often than higher, and the rewrites carry the model's memory |
| Ask for the search `question` in English in the `search_labels` description | 8 → 6 of 16 searches in German | none | gpt-oss-20b mostly ignores it |

The two prompts stay in `prompts/rag/` so the measurement can be repeated. Since #446 both steps are also a setting of the app, `QUERY_TRANSLATION=translate` or `multi_query`, off by default as this eval found; the eval keeps its own copy of the steps, so these numbers reproduce as they are.

## Limits

- One model, gpt-oss-20b, and one sample of each translation and rewrite: a difference of 3 questions is within what another sample could move. gpt-6-luna, the cloud chat model, wasn't measured; it may follow the tool description better.
- The German questions were written by the session that ran the eval, not by German-speaking users, and keep the English brand names. Questions with German brand names (Ibuflam, Novalgin) are name recognition (#113), measured elsewhere.
- The section boost the agent's `section` argument gives is left out, like in the embedding comparison. #114's comment on "How does imatinib work?" (pharmacokinetics passages above mechanism of action) is a ranking question for a re-ranker or hybrid search (#96, #44), not for translation.
- The chat runs use 19 questions; their counts show a direction, not a rate.

## Reproduce

```
cd backend
OFFLINE=1 LOCAL_LLM_BASE_URL=http://localhost:1234/v1 LOCAL_LLM_MODEL=openai/gpt-oss-20b \
    uv run python -m evals.retrieval.query_translation
OFFLINE=1 LOCAL_LLM_BASE_URL=http://localhost:1234/v1 LOCAL_LLM_MODEL=openai/gpt-oss-20b \
    uv run python -m evals.chat_model.search_language
```

The model's translations and rewrites are cached in `data/build/eval/query_translation/` (`openai_gpt-oss-20b-e351284738e4.jsonl`), the chat answers in `data/build/eval/search_language/`. The second chat run added "Write it in English whatever language the user writes in, keeping the drug names as the user wrote them: the labels are in English, and an English question finds the passage more often." after the first sentence on `question` in the `search_labels` docstring; that change isn't kept.
