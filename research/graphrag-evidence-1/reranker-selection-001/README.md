# Reranker selection and prospective B configuration

## Candidate choice

Select Alibaba-NLP/gte-multilingual-reranker-base for a bounded CPU smoke next.
Its official metadata explicitly lists Korean and declares Apache-2.0. This is
language-support metadata, not measured Korean manufacturing relevance. Its
custom NewForSequenceClassification depends on the separate Alibaba-NLP/new-impl
repository; both revisions are pinned in prospective-b-config.json. Standard
ONNX weights were not listed in the inspected official tree. No weights or
custom model code were executed in this cycle; runtime feasibility is unmeasured.

| Candidate | Observed source declaration | Decision for next smoke |
|---|---|---|
| GTE multilingual reranker | ko listed; Apache-2.0; custom implementation | selected provisionally |
| BGE reranker v2 m3 | multilingual; Apache-2.0; standard XLM-R architecture | not selected; Korean task quality unmeasured |
| Jina reranker v2 multilingual | multilingual; CC BY-NC4.0; official ONNX files | not selected for this plan |

Sources: [GTE](https://huggingface.co/Alibaba-NLP/gte-multilingual-reranker-base),
[BGE](https://huggingface.co/BAAI/bge-reranker-v2-m3),
[Jina](https://huggingface.co/jinaai/jina-reranker-v2-base-multilingual).
These are model-card declarations, not complete license/legal or security audits.
No recommendation to redistribute third-party weights is made. Saved headers in
new-impl code declare Apache2.0; preserve notices and inspect full code before use.

## Tokenizer diagnostic

Pinned GTE tokenizer with tokenizers0.22.1 encoded all24 x1483=35,592 possible
question/child pairs without truncation; maximum560tokens and0pairs over1024.
This is an input-size diagnostic, not reranker inference or a relevance score.
No reference-answer file was read. Existing A outputs and consumed cohort remain
unchanged. Complete per-question minima/maxima and source hashes are retained.

## Prospective comparison

```text
Same shared search children and original questions
  +-- existing E5 dense top10 --+
  +-- BM25 lexical top10 ------+-> deduplicated union <=20
                                -> pinned reranker (not run)
                                -> max score per parent, top8
                                -> same A whole-parent accounting budgets
```

BM25 details and deterministic ordering are fixed in the JSON before any B run.
Do not fill overlapping candidate slots using gold or alternative sources. B-A
changes retrieval mixture and reranking together; it cannot isolate either cause.
The same final evidence/candidate caps do not imply equal CPU cost. C/E must use
identical saved B seeds; D must receive exact C selected evidence with no lookup.
Actual generator tokenizer and answer budgets remain unselected; no generation.

Source snapshots, tokenizer and receipts stay under ignored
_workspace/graphrag-cycle8/sources/. Model revision8215cf04918ba6f7b6a62bb44238ce2953d8831c;
custom code revision40ced75c3017eb27626c9d4ea981bde21a2662f4. Official weight metadata
reports611,934,706bytes; weights not acquired here. Selection is before B outcomes,
not a model sweep or tuning to recover failed A answers. A0/18authored support is
preserved and is not a general vectorRAG result. Next gate is a bounded CPU smoke.
