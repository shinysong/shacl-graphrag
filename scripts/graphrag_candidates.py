"""Deterministic pre-reranker candidates; no references, model or source lookup."""
from collections import Counter
import math
import re


def terms(text):
    return re.findall(r"[^\W\d_]+|\d+", text.casefold())


def candidates(children, question, dense_scores):
    """Union dense top10 and positive BM25 top10; never fill overlap slots."""
    ids = [c["child_id"] for c in children]
    if not ids or len(set(ids)) != len(ids) or len(dense_scores) != len(ids):
        raise ValueError("empty/duplicate/index mismatch")
    if any(not isinstance(x, str) or not x for x in ids):
        raise ValueError("invalid child ID")
    if not isinstance(question, str):
        raise ValueError("question must be text")
    scores = [float(x) for x in dense_scores]
    if any(isinstance(x, bool) for x in dense_scores) or not all(map(math.isfinite, scores)):
        raise ValueError("nonfinite or boolean dense score")
    docs = [Counter(terms(c["search_text"])) for c in children]
    lengths = [sum(d.values()) for d in docs]
    n = len(docs)
    average = sum(lengths) / n
    df = Counter(t for d in docs for t in d)
    query = sorted(set(terms(question)))
    lexical = []
    for child_id, doc, length in zip(ids, docs, lengths):
        value = 0.0
        if average:
            for term in query:
                tf = doc[term]
                if tf:
                    idf = math.log1p((n - df[term] + 0.5) / (df[term] + 0.5))
                    value += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * length / average))
        if not math.isfinite(value):
            raise ValueError("nonfinite lexical score")
        if value > 0:
            lexical.append({"child_id": child_id, "score": value})
    lexical.sort(key=lambda h: (-h["score"], h["child_id"]))
    lexical = lexical[:10]
    dense = sorted((dict(child_id=i, score=s) for i, s in zip(ids, scores)),
                   key=lambda h: (-h["score"], h["child_id"]))[:10]
    union = sorted({h["child_id"] for h in dense + lexical})
    return {"dense": dense, "lexical": lexical, "candidate_child_ids": union,
            "candidate_count": len(union), "overlap_count": len(dense) + len(lexical) - len(union),
            "corpus_documents": n, "average_document_length": average,
            "status": "ready_for_reranker", "reranking_executed": False}
