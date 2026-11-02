# Review scope and remaining runtime checks

Both independent reviews accepted the candidate contract/module only. The implementation reviewer independently verified ten file hashes. Neither reviewer executed tests or a model.

The future loader must verify all hashes and array float32 dtype, shapes, finiteness, unit norms and child/question order. In particular, reject NumPy boolean arrays before calling candidates: the module rejects Python bool values but this does not establish NumPy boolean rejection. Add a boundary regression with the loader.

No fixed-source candidates, reranker outputs or final B evidence have been produced. Pinned custom-code inspection, dependencies, local loader, bounded CPU smoke, resource/failure records and separate execution review remain necessary. Paid API authorization remains zero; local preparation does not authorize paid calls.
