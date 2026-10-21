# German against English answers, 2026-10-21

> **Answer:** A German question gets as good an answer as its English original. On gpt-oss-20b all 44 German answers were written in German, a label search returned an answering passage for 43 of 44 (English 42 of 45), and the source check found 0.82 of the German claims supported by the passage they cite (English 0.77). Nothing needs fixing in the agent. What German adds is small: the guard answered one general German question as personal advice in one of three runs, and one answer mistranslated heartburn as "Herzrasen" (racing heart), which the source check let through.

#357 asked whether German answers drift into English or lose faithfulness. Search is measured already: German questions find the answering passage for 0.80 of the 94 retrieval questions against 0.85 in English, filtered to the drug ([query translation](query-translation-2026-10-16.md), #114). This measures the answers. It runs after the German drug names (#355), so Sertralin or Methylphenidat no longer fail as unknown names. The baseline is `main` at 8d912be, on the store refreshed with those names.

## Setup

- **Questions:** 15 of the retrieval questions (`backend/evals/datasets/retrieval_questions.yaml`) and their German versions (`retrieval_questions_de.yaml`), with the same answer key: the drug and one of its answering passages. One per section group, plus one more where the German generic name differs (Paracetamol, Lamotrigin, Methylphenidat; also Omeprazol, Finasterid, Famotidin, Cetirizin, Pseudoephedrin, Tizanidin). Left out: overdose and abuse questions, where the guard's emergency text would decide the language, and the four general German questions #114 saw the guard answer as personal advice. The list is `PAIRS` in `backend/evals/multilang/run.py`.
- **Chat:** each question asked 3 times in each language through `POST /chat` in-process, guard and source check included, with the chat limits off. `openai/gpt-oss-20b` in LM Studio, 32,768 tokens of context, one slot, answers at medium reasoning, `OFFLINE=1`. 90 answers.
- **Scored by script:**
  - **Language:** the share of German among the German and English function words in the answer (der, und, ist … against the, and, is …), citation numbers left out. 0.7 or more is German, 0.3 or less English, between is mixed. A German answer that quotes an English label sentence stays well above 0.7.
  - **Search:** whether a `search_labels` call returned a passage of the answer key among its first five, as in `evals/chat_model/search_language.py`.
  - **Source check:** the verdicts of the chat's own source check (#43, `guard/source_check.py`) in the answer's `source_check` event, so no second judge runs.
- **By hand:** every claim the check marked unsupported (5), and the German answers of the first run.

## Result

| | German | English |
|---|---|---|
| Answers | 45 | 45 |
| Failed | 0 | 0 |
| Fixed answer from the guard | 1 | 0 |
| Written in the question's language | 44 of 44 | 45 of 45 |
| German function-word share, median | 1.00 | 0.00 |
| Label searches written in German | 27 of 46 | 0 of 45 |
| Answering passage in a search's top 5 | 43 of 44 | 42 of 45 |
| Claims supported | 75 | 59 |
| Claims held elsewhere | 13 | 17 |
| Claims unsupported | 4 | 1 |
| Not a claim | 1 | 1 |
| Claims supported, of all claims | 0.82 (75 of 92) | 0.77 (59 of 77) |
| Seconds per answer, median | 22.9 | 20.8 |

Rows after "Fixed answer" count the answers the agent wrote, without the guard's fixed answer. The source check ran on every one.

## What it shows

- **German answers stay German.** Every one is written in German throughout (share 1.00 in the median, none mixed), with the label's figures and the same citations as the English answers. The agent prompt says "Answer in the language of the user's question" (`prompts/agent/system.md`), and gpt-oss-20b does. Passing the guard's detected language to the agent, the fix the issue named in case of drift, isn't needed.
- **Search keeps up because the agent often translates.** 19 of 46 German-question searches were written in English. The one question with a clear difference goes the other way: "Welche Nebenwirkungen bekommen Menschen unter Imatinib am häufigsten?" found the answering passage in all 3 runs, its English original "What side effects do people most often get on imatinib?" in none. The only other miss is one German run that searched the Cetirizin syrup's parabens under warnings.
- **German answers are as faithful.** The share of supported claims is a little higher in German (0.82 against 0.77). That is within the run's noise: most of the gap is "held elsewhere", a true sentence without its own citation, which both languages produce when they cite once at the end of a paragraph. Of the 4 German claims marked unsupported, 2 add a fact from memory ("Dauer und Schwere der Symptome" for Valtrex, "schwerwiegende Nebenwirkungen" for pseudoephedrine with MAO inhibitors). The other 2 are the check's mistakes: Valtrex lowering the chance of spreading herpes is in source 3, which the answer cites, and fewer outbreaks are in source 1. The one English claim adds a definition of erosive esophagitis.
- **A German translation slip passes the check.** One Famotidin answer lists "Herzrasen" (racing heart) where the label says heartburn ("Sodbrennen"). The source check, reading the English passage, marked it held elsewhere. It judges whether the content is in the sources and can't tell a mistranslated word from a paraphrase. It was 1 of 45 German answers.
- **The guard sorts a general German question as personal advice now and then.** "Dürfen Menschen mit schwerer Nierenerkrankung Metformin nehmen?" got the personal-advice text in 1 of 3 runs. Its English version never did. #114 saw the same kind of question refused, and #236 and #288 tuned the input check for it. It stays a gpt-oss-20b limit offline (Jev sorts online).
- **German costs 2 seconds.** 22.9 s against 20.8 s per answer in the median.
- **Found along the way:** the claim splitter cuts "1,8 Mio. Schwangerschaften" into two claims, because "Mio" isn't in its abbreviation list (`ABBREVIATIONS` in `guard/claims.py`). The source check then judges the fragment "Eine retrospektive Kohortenstudie mit 1,8 Mio." as not a claim. Filed as #365.

## Limits

- 15 pairs, 3 runs, one model. The differences in search and supported claims are a few answers each and go both ways between runs. The run shows there is no gap, but it can't measure a small one.
- The source check is the same gpt-oss-20b with an English prompt, judging a German claim against English passages. A difference in its verdicts mixes the answer's quality with how the check reads German. The hand read of the unsupported claims found 2 of its 4 German rejections wrong and 0 of its 1 English one, so the German answers are, if anything, a little better than the table says.
- The language test counts function words. It would miss an English term left in a German sentence ("Rash" in brackets, which it should), and it can't judge how good the German is. The first run's German answers were read by hand: plain, correct German with one mistranslated word.
- Cloud models (gpt-6-luna) and Jev's input check are not measured; they run only with `OFFLINE=0`.

## Reproduce

```
cd backend
OFFLINE=1 LOCAL_LLM_BASE_URL=http://localhost:1234/v1 LOCAL_LLM_MODEL=openai/gpt-oss-20b \
    uv run python -m evals.multilang.run --times 3
```

About 35 minutes for 90 answers. Answers are cached in `data/build/eval/multilang/`, keyed by the model, every prompt file and the tool descriptions; this run is `openai_gpt-oss-20b-answer-medium-check-medium-5a8ca37fbfef.jsonl`, so the same command prints this table again without a model.
