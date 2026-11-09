# Eight standalone Korean paper reviews
User requests eight standalone paper review blog posts and publication on existing GitHub Pages. No research experiments, paid calls or AWS. Review source-grounding, accurate methods/results/limitations, proper distinction of author reports versus reviewer interpretations. Prior review preference: explain each paper independently, not our own repository experiments.

Allowed read-only source material: docs/journal/2026-11-05-review-*.md (eight drafts), _workspace/semantic-reviews-20261105/sources/*.txt and *.pdf, sources/acquisition.json, sources/images/*.png. Review ALL eight articles, verify important numbers and qualifiers against cached primary full texts. Sources not redistributed. Native main inspected selected source images and extracted sections; no reproduced benchmark claims.

Methods reviewer: material factual errors, denominators, inferred versus measured claims, theorem scope, unsupported novelty, metadata. Implementation reviewer: Markdown/editable Mermaid/URLs, privacy, independent readable posts, publication scope. Both may read source PDFs/text as needed. Write no source changes. Do not read one another's outputs, secrets, historical QA gold or other workspace data.

Publish strategy: isolated worktree _workspace/semantic-reviews-20261105/publish at fcacb1415de50900dc9a149ce7ef189a7f068ea3. Only eight posts plus journal/index.md built from base+eight links. Main dirty experiments/index remain intact. MkDocs strict and Chirpy build, then Chromium desktop/mobile light/dark checks and live checks required before claiming successful publication. No registered research checks (checks=[]); build/browser logs are separate observed documentation checks. Pending checks must be labeled pending, not invented.

Korean humanization performed via native roles. Light7, standard1. Source-preservation gates pass except one footnote detector false-positive on unchanged arxiv URL numeral; independent finalizer inspected and accepted, warning retained.

Revision 2: Independent review prompted two changes only: explicitly limit dual-path retrieval cost to Integration and state consistency in the normalized Horn-ALCHIQ knowledge-base precondition. Primary arxiv metadata HTML is now cached under sources/*-metadata.html; these confirm PolicyKG under review, SHACL updates ISWC acceptance, xpSHACL colocated workshop acceptance. Allowed to inspect those HTML files. Prior eight articles were fully reviewed; focus on revised claims and unchanged hash bindings. Do not read other reviewers outputs. Documentation builds and 24 browser cases passed before these prose-only changes; final rebuild pending. No 16 GiB build-resource claim is made.

Frozen article hashes:
{
  "docs/journal/2026-11-05-review-clinical-ontology-rag.md": "1789c9e009d3924dc5a9b68cbd4f390ab27fe8369a809e04e58c99b252dee592",
  "docs/journal/2026-11-05-review-owl-shacl-semantics.md": "31f1fd20a4ec26d4f72e78cdbda60690316e2fa6196180aae3c99c3198b07423",
  "docs/journal/2026-11-05-review-policykg.md": "97e7880736d01cc023ece2ddb09c1f3f2bd7a1dbd05cc4ec6028dbb340fe0a53",
  "docs/journal/2026-11-05-review-rag-vs-graphrag.md": "87c96a43e9d963ac10b3242e605c8eef66a1b7c419bb931477a8bd264067e4d7",
  "docs/journal/2026-11-05-review-rdf2pg.md": "2c96f5f6de61e4ee86a2ffaa49d3b35f46cf8e660bee0774f60359b7c8b3341f",
  "docs/journal/2026-11-05-review-shacl-updates.md": "39c563e077a9e80bb0810bd0b12340932ff7102764622d8e063a4266a92521c9",
  "docs/journal/2026-11-05-review-when-graphs-rag.md": "ae5943f01bd06e99169e0d99d8e2de452401bb51531c2151db98f592cd1655f4",
  "docs/journal/2026-11-05-review-xpshacl.md": "b94cfc704c7407229fb19b4be86b8882f12279d62c3d1d9eec7a06c5d9cc7234"
}
