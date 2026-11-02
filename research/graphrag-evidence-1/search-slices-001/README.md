# Lossless search input diagnostic

```text
814 preserved source chunks
       | exact Unicode slices + parent IDs (implemented)
       v
1,483 search children, each <=512 E5 tokens
       | dense/lexical retrieval (not run)
       v
child scores --> max score per parent (helper tested)
       | future full-evidence packing, same budgets for all arms
       v
A/B/C/E evidence --> D receives exact C evidence only
```

298 parents split into up to4 children;814/814 original texts reconstructed
exactly. All1,483 complete search strings were independently re-encoded by the
coordinator, including prefixes/special tokens; maximum512. This is a software
input diagnostic on consumed data, not measured retrieval effectiveness.

Manual checks:33 unit tests passed (28 prior+5 new); builder exit0; round-trip,
identity/hash and re-tokenization audit exit0. No embeddings, reranker, generation
or SHACL calls. Slices may break semantic units or JSON; long parents have more
search opportunities. Full-source preservation does not establish comprehension.

Source corpus and prior results unchanged. Pinned tokenizer remains ignored at
`_workspace/graphrag-cycle3/sources/e5-tokenizer.json`; acquisition URL and hash
are recorded there and in dense-readiness-001. Frozen code/protocol copies support
reproduction. Runtime model/generator tokenizer and full evidence budgets pending.
