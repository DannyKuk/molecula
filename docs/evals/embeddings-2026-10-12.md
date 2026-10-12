# Embedding comparison, 2026-10-12

## With the completed answer key

The report of `python -m evals.retrieval.rescore data/build/eval/embeddings-20261012T122048Z.json` with the completed answer key (commit 3859155), as printed. Query times here were measured on the GPU or through OpenRouter; CPU query times and the reading of these numbers are in [the decision doc](../decisions/embeddings.md).

94 questions. In drug: searched within the question's drug. Query time: one question, after warm-up.

| Model | Dims | R@1 in drug | R@5 in drug | MRR@10 in drug | R@5 whole index | MRR@10 whole index | Embed chunks (s) | Index (MB) | Query p50 / p95 (ms) |
|---|---|---|---|---|---|---|---|---|---|
| bge-small | 384 | 0.56 | 0.80 | 0.666 | 0.74 | 0.624 | 10 (cuda:0, 0.2 GB) | 106.8 | 6 / 7 (cuda:0) |
| bge-small+instruction | 384 | 0.59 | 0.78 | 0.672 | 0.73 | 0.640 | 10 (cuda:0, 0.2 GB) | 106.9 | 6 / 7 (cuda:0) |
| medembed-small | 384 | 0.51 | 0.79 | 0.640 | 0.73 | 0.574 | 10 (cuda:0, 0.2 GB) | 106.9 | 6 / 7 (cuda:0) |
| bge-large | 1024 | 0.59 | 0.87 | 0.694 | 0.78 | 0.627 | 35 (cuda:0, 0.9 GB) | 135.1 | 11 / 12 (cuda:0) |
| bge-large+instruction | 1024 | 0.57 | 0.88 | 0.691 | 0.80 | 0.625 | 35 (cuda:0, 0.9 GB) | 135.1 | 11 / 13 (cuda:0) |
| modernbert-embed | 768 | 0.53 | 0.83 | 0.658 | 0.74 | 0.586 | 23 (cuda:0, 0.7 GB) | 120.3 | 11 / 12 (cuda:0) |
| bge-m3 | 1024 | 0.50 | 0.85 | 0.644 | 0.76 | 0.572 | 37 (cuda:0, 1.7 GB) | 135.1 | 11 / 14 (cuda:0) |
| qwen3-0.6b | 1024 | 0.59 | 0.83 | 0.686 | 0.73 | 0.623 | 80 (cuda:0, 2.7 GB) | 135.2 | 22 / 23 (cuda:0) |
| qwen3-4b | 2560 | 0.70 | 0.94 | 0.797 | 0.88 | 0.754 | 359 (cuda:0, 11.4 GB) | 210.4 | 29 / 30 (cuda:0) |
| qwen3-8b | 4096 | 0.70 | 0.97 | 0.818 | 0.91 | 0.758 | 624 (cuda:0, 18.8 GB) | 288.5 | 39 / 41 (cuda:0) |
| cloud:text-embedding-3-small | 1536 | 0.60 | 0.86 | 0.720 | 0.83 | 0.665 | 157 (openrouter) | 159.4 | 441 / 874 (openrouter) |
| cloud:text-embedding-3-large | 3072 | 0.68 | 0.97 | 0.796 | 0.93 | 0.752 | 188 (openrouter) | 237.4 | 577 / 730 (openrouter) |
| cloud:gemini-embedding-2 | 3072 | 0.71 | 0.98 | 0.829 | 0.98 | 0.795 | 206 (openrouter) | 237.4 | 314 / 438 (openrouter) |
| cloud:qwen3-8b | 4096 | 0.69 | 0.97 | 0.813 | 0.93 | 0.751 | 496 (openrouter) | 288.5 | 489 / 5713 (openrouter) |

Recall@5 in drug by section group:

| Section group | n | bge-small | bge-small+instruction | medembed-small | bge-large | bge-large+instruction | modernbert-embed | bge-m3 | qwen3-0.6b | qwen3-4b | qwen3-8b | cloud:text-embedding-3-small | cloud:text-embedding-3-large | cloud:gemini-embedding-2 | cloud:qwen3-8b |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abuse_dependence | 7 | 0.86 | 0.86 | 0.71 | 0.71 | 0.71 | 0.71 | 0.71 | 0.86 | 0.86 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| adverse_reactions | 7 | 0.71 | 0.71 | 0.71 | 1.00 | 0.86 | 0.86 | 0.86 | 0.86 | 1.00 | 1.00 | 0.71 | 0.86 | 1.00 | 1.00 |
| clinical_studies | 7 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.86 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| contraindications | 7 | 0.86 | 0.86 | 0.86 | 0.86 | 0.86 | 0.86 | 0.86 | 0.86 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| dosing | 7 | 0.71 | 0.71 | 0.71 | 1.00 | 1.00 | 0.86 | 1.00 | 1.00 | 1.00 | 1.00 | 0.71 | 1.00 | 1.00 | 1.00 |
| indications | 7 | 0.86 | 0.86 | 0.86 | 1.00 | 1.00 | 0.86 | 0.86 | 0.86 | 0.86 | 1.00 | 0.71 | 1.00 | 1.00 | 1.00 |
| interactions | 7 | 1.00 | 0.71 | 0.86 | 0.86 | 1.00 | 1.00 | 0.86 | 0.57 | 0.86 | 1.00 | 0.71 | 1.00 | 1.00 | 1.00 |
| otc_consumer | 3 | 0.67 | 1.00 | 0.67 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.67 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| overdosage | 7 | 0.57 | 0.57 | 0.71 | 0.86 | 0.86 | 0.57 | 1.00 | 0.86 | 1.00 | 0.86 | 1.00 | 1.00 | 1.00 | 0.86 |
| patient_information | 7 | 0.86 | 0.86 | 0.86 | 0.71 | 0.71 | 0.71 | 0.86 | 1.00 | 1.00 | 1.00 | 0.86 | 1.00 | 1.00 | 1.00 |
| pharmacology | 7 | 0.43 | 0.29 | 0.43 | 0.57 | 0.57 | 0.57 | 0.57 | 0.57 | 1.00 | 1.00 | 0.71 | 0.86 | 1.00 | 1.00 |
| product | 7 | 0.86 | 0.86 | 0.86 | 0.71 | 0.86 | 0.86 | 0.86 | 0.57 | 0.71 | 0.86 | 0.86 | 0.86 | 0.86 | 0.86 |
| specific_populations | 7 | 0.71 | 0.71 | 0.71 | 1.00 | 1.00 | 0.86 | 0.71 | 0.86 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| warnings | 7 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.86 | 1.00 | 0.86 | 0.86 | 1.00 | 0.86 | 0.86 |

Missed in drug at 5 by bge-small: imatinib-mechanism, apixaban-indication, escitalopram-depression-dose, lisinopril-angioedema, imatinib-common-side-effects, zolpidem-abuse-dependence, lamotrigine-dosing, diclofenac-otc-consumer, carbamazepine-overdosage, haloperidol-overdosage, diclofenac-overdosage, losartan-patient-information, esomeprazole-pharmacology, valacyclovir-pharmacology, oseltamivir-pharmacology, esomeprazole-product, sumatriptan-specific-populations, morphine-specific-populations, ondansetron-adverse-reactions
Missed in drug at 5 by bge-small+instruction: imatinib-mechanism, apixaban-indication, escitalopram-depression-dose, lisinopril-angioedema, imatinib-common-side-effects, zolpidem-abuse-dependence, lamotrigine-dosing, carvedilol-interactions, phenytoin-interactions, carbamazepine-overdosage, haloperidol-overdosage, diclofenac-overdosage, losartan-patient-information, acetaminophen-pharmacology, esomeprazole-pharmacology, valacyclovir-pharmacology, oseltamivir-pharmacology, esomeprazole-product, sumatriptan-specific-populations, morphine-specific-populations, ondansetron-adverse-reactions
Missed in drug at 5 by medembed-small: imatinib-mechanism, apixaban-indication, escitalopram-depression-dose, lisinopril-angioedema, imatinib-common-side-effects, tramadol-abuse-dependence, zolpidem-abuse-dependence, lamotrigine-dosing, carvedilol-interactions, diclofenac-otc-consumer, haloperidol-overdosage, diclofenac-overdosage, losartan-patient-information, esomeprazole-pharmacology, valacyclovir-pharmacology, oseltamivir-pharmacology, esomeprazole-product, sumatriptan-specific-populations, morphine-specific-populations, ondansetron-adverse-reactions
Missed in drug at 5 by bge-large: imatinib-mechanism, lisinopril-angioedema, tramadol-abuse-dependence, zolpidem-abuse-dependence, phenytoin-interactions, haloperidol-overdosage, losartan-patient-information, semaglutide-patient-information, esomeprazole-pharmacology, valacyclovir-pharmacology, esomeprazole-product, methylphenidate-product
Missed in drug at 5 by bge-large+instruction: imatinib-mechanism, lisinopril-angioedema, imatinib-common-side-effects, tramadol-abuse-dependence, zolpidem-abuse-dependence, haloperidol-overdosage, losartan-patient-information, semaglutide-patient-information, esomeprazole-pharmacology, valacyclovir-pharmacology, esomeprazole-product
Missed in drug at 5 by modernbert-embed: imatinib-mechanism, apixaban-indication, lisinopril-angioedema, imatinib-common-side-effects, tramadol-abuse-dependence, zolpidem-abuse-dependence, lamotrigine-dosing, carbamazepine-overdosage, haloperidol-overdosage, diclofenac-overdosage, losartan-patient-information, semaglutide-patient-information, esomeprazole-pharmacology, valacyclovir-pharmacology, esomeprazole-product, nicotine-specific-populations
Missed in drug at 5 by bge-m3: imatinib-mechanism, apixaban-indication, lisinopril-angioedema, imatinib-common-side-effects, tramadol-abuse-dependence, zolpidem-abuse-dependence, risperidone-clinical-studies, carvedilol-interactions, semaglutide-patient-information, valacyclovir-pharmacology, oseltamivir-pharmacology, esomeprazole-product, nicotine-specific-populations, sumatriptan-specific-populations
Missed in drug at 5 by qwen3-0.6b: imatinib-mechanism, apixaban-indication, simvastatin-cyp3a4, lisinopril-angioedema, imatinib-common-side-effects, tramadol-abuse-dependence, carvedilol-interactions, phenytoin-interactions, haloperidol-overdosage, valacyclovir-pharmacology, oseltamivir-pharmacology, dexamethasone-product, esomeprazole-product, levothyroxine-product, sumatriptan-specific-populations, celecoxib-warnings
Missed in drug at 5 by qwen3-4b: apixaban-indication, zolpidem-abuse-dependence, phenytoin-interactions, diclofenac-otc-consumer, dexamethasone-product, esomeprazole-product
Missed in drug at 5 by qwen3-8b: haloperidol-overdosage, esomeprazole-product, celecoxib-warnings
Missed in drug at 5 by cloud:text-embedding-3-small: imatinib-mechanism, apixaban-indication, atorvastatin-starting-dose, simvastatin-cyp3a4, imatinib-common-side-effects, lamotrigine-dosing, omeprazole-indications, phenytoin-interactions, semaglutide-patient-information, oseltamivir-pharmacology, esomeprazole-product, celecoxib-warnings, ondansetron-adverse-reactions
Missed in drug at 5 by cloud:text-embedding-3-large: imatinib-common-side-effects, oseltamivir-pharmacology, esomeprazole-product
Missed in drug at 5 by cloud:gemini-embedding-2: esomeprazole-product, celecoxib-warnings
Missed in drug at 5 by cloud:qwen3-8b: haloperidol-overdosage, esomeprazole-product, celecoxib-warnings

## The run with the first answer key

The same run as scored when it was made (2026-10-12, `data/build/eval/embeddings-20261012T122048Z.json`), before `pooled_evidence` existed: only the passage each question was written from counted.

| Model | Dims | R@1 in drug | R@5 in drug | MRR@10 in drug | R@5 whole index | MRR@10 whole index | Embed chunks (s) | Index (MB) | Query p50 / p95 (ms) |
|---|---|---|---|---|---|---|---|---|---|
| bge-small | 384 | 0.44 | 0.72 | 0.562 | 0.67 | 0.521 | 10 (cuda:0, 0.2 GB) | 106.8 | 6 / 7 (cuda:0) |
| bge-small+instruction | 384 | 0.47 | 0.71 | 0.578 | 0.67 | 0.545 | 10 (cuda:0, 0.2 GB) | 106.9 | 6 / 7 (cuda:0) |
| medembed-small | 384 | 0.38 | 0.72 | 0.539 | 0.67 | 0.473 | 10 (cuda:0, 0.2 GB) | 106.9 | 6 / 7 (cuda:0) |
| bge-large | 1024 | 0.46 | 0.78 | 0.586 | 0.68 | 0.515 | 35 (cuda:0, 0.9 GB) | 135.1 | 11 / 12 (cuda:0) |
| bge-large+instruction | 1024 | 0.47 | 0.82 | 0.601 | 0.72 | 0.530 | 35 (cuda:0, 0.9 GB) | 135.1 | 11 / 13 (cuda:0) |
| modernbert-embed | 768 | 0.41 | 0.74 | 0.567 | 0.66 | 0.493 | 23 (cuda:0, 0.7 GB) | 120.3 | 11 / 12 (cuda:0) |
| bge-m3 | 1024 | 0.40 | 0.79 | 0.561 | 0.67 | 0.489 | 37 (cuda:0, 1.7 GB) | 135.1 | 11 / 14 (cuda:0) |
| qwen3-0.6b | 1024 | 0.46 | 0.77 | 0.589 | 0.67 | 0.526 | 80 (cuda:0, 2.7 GB) | 135.2 | 22 / 23 (cuda:0) |
| qwen3-4b | 2560 | 0.55 | 0.87 | 0.681 | 0.82 | 0.638 | 359 (cuda:0, 11.4 GB) | 210.4 | 29 / 30 (cuda:0) |
| qwen3-8b | 4096 | 0.54 | 0.89 | 0.697 | 0.84 | 0.639 | 624 (cuda:0, 18.8 GB) | 288.5 | 39 / 41 (cuda:0) |
| cloud:text-embedding-3-small | 1536 | 0.51 | 0.81 | 0.647 | 0.78 | 0.594 | 157 (openrouter) | 159.4 | 441 / 874 (openrouter) |
| cloud:text-embedding-3-large | 3072 | 0.56 | 0.91 | 0.704 | 0.87 | 0.660 | 188 (openrouter) | 237.4 | 577 / 730 (openrouter) |
| cloud:gemini-embedding-2 | 3072 | 0.62 | 0.93 | 0.745 | 0.93 | 0.711 | 206 (openrouter) | 237.4 | 314 / 438 (openrouter) |
| cloud:qwen3-8b | 4096 | 0.53 | 0.90 | 0.695 | 0.86 | 0.635 | 496 (openrouter) | 288.5 | 489 / 5713 (openrouter) |


## CPU query times

The CPU-sized models with `--device cpu` on an Intel Core Ultra 7 265K (`data/build/eval/embeddings-20261012T122456Z.json`), first answer key. Chunk vectors came from the GPU build; only the questions were embedded on the CPU.

| Model | Dims | R@1 in drug | R@5 in drug | MRR@10 in drug | R@5 whole index | MRR@10 whole index | Embed chunks (s) | Index (MB) | Query p50 / p95 (ms) |
|---|---|---|---|---|---|---|---|---|---|
| bge-small | 384 | 0.44 | 0.72 | 0.562 | 0.67 | 0.521 | 10 (cuda:0, 0.2 GB) | 106.9 | 8 / 9 (cpu) |
| bge-small+instruction | 384 | 0.47 | 0.71 | 0.578 | 0.67 | 0.545 | 10 (cuda:0, 0.2 GB) | 106.9 | 8 / 9 (cpu) |
| medembed-small | 384 | 0.38 | 0.72 | 0.539 | 0.67 | 0.473 | 10 (cuda:0, 0.2 GB) | 106.9 | 8 / 10 (cpu) |
| bge-large | 1024 | 0.46 | 0.78 | 0.586 | 0.68 | 0.515 | 35 (cuda:0, 0.9 GB) | 135.2 | 36 / 39 (cpu) |
| bge-large+instruction | 1024 | 0.47 | 0.82 | 0.601 | 0.72 | 0.530 | 35 (cuda:0, 0.9 GB) | 135.1 | 39 / 42 (cpu) |
| modernbert-embed | 768 | 0.41 | 0.74 | 0.567 | 0.66 | 0.493 | 23 (cuda:0, 0.7 GB) | 120.3 | 18 / 20 (cpu) |
| bge-m3 | 1024 | 0.40 | 0.79 | 0.561 | 0.67 | 0.489 | 37 (cuda:0, 1.7 GB) | 135.1 | 37 / 42 (cpu) |
| qwen3-0.6b | 1024 | 0.45 | 0.77 | 0.581 | 0.67 | 0.519 | 80 (cuda:0, 2.7 GB) | 135.2 | 67 / 75 (cpu) |


## The app's index

`python -m molecula.ingest index` with `BAAI/bge-m3` on the RX 7900 XTX, 2026-10-12:

```
7012 chunks from 156 labels embedded with BAAI/bge-m3 in 92 s; index 135.1 MB
```
