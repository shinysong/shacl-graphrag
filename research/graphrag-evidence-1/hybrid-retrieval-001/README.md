# Hybrid retrieval evidence envelopes

B evidence packing completed all24 consumed development questions with0packing failures and0new model calls. The unchanged A rank_pack implementation and pinned E5 tokenizer0.22.1 selected whole source parents using max-child scores, top8 parents and4096token/64000byte caps. No answer labels or new source lookup were used.

```text
Saved453 logits -> max child per parent -> top8 parents
 -> same A whole-parent accounting caps
 ->24 B evidence envelopes
 -> later offline support scoring and matched C/E expansion
```

The selected envelopes contain168 occurrences:149edge and19node chunks. There were24parent skips for budget limits. Maximum selected evidence was3876E5 accounting tokens and6352bytes. Occurrences are not distinct records or independent cases. Generator evidence_tokens remains null. No relevance, support completeness, answer accuracy or graph benefit is established by these counts.

Eight unit checks passed. Both independent implementation/design reviews accepted packing before execution. The first coordinator postrun audit failed at composition counting because it read kind instead of chunk_type; the original failed script and exit1 are retained. Packing outputs were not changed. A separate review job examined the corrected audit; the only correction was the field name. Its execution returned0 and checked all24payloads and12hashes. An independent reviewer also recomputed current packing and checked selected/seed IDs.

The audit script itself compares seed IDs with selected IDs but does not directly bind those IDs to payload IDs; present-row identity was checked separately by reviewers. Do not treat the script alone as a general seed-identity validator. A future C/E runner must enforce that binding.

B seeds are selected evidence only; historical A seed metadata named prepacking parents. Actual A/B evidence packing caps are unchanged. Future C/E must use identical selected B seeds, and D exact C evidence. Original A results, frozen candidates and scores remain unchanged. Global CLI failure paths and memory usage were not measured in this step. Private tokenizer paths require the documented prepared workspace.
