# Research and demonstration index

This directory indexes already consumed manufacturing and auxiliary SBOM work.
The 25 entries are explanatory questions, not a new statistical denominator or
a new paid launch. Catalog 001 is preserved byte-for-byte; its original question
texts and historical measurement notes remain in this version. Six later entries
explicitly identify their own evidence and limitations. The W-Q8a paid question is
a separately frozen extension, not a retroactive evaluation of W-Q8's wording.

`executed-query-excerpts.json` contains three exact AST source spans of the
executed live adapter: `Neo.query`, `sparql` and external `triples` materialization.
The source SHA-256 matches the 17:11:22 prelaunch-v4 receipt. An earlier freeze
belongs to the preserved pre-fix implementation and has a different hash.
These excerpts intentionally omit resource configuration and are not a complete
executable deployment package or authorization to restart resources.

`build_presentation.py` regenerates the existing static manufacturing demo through
its preserved upstream builder, then replaces one introductory paragraph with
source-scope labels and navigation. It reads saved artifacts only. It does not
join the Penelope measurements to OPC UA model objects, alter experimental
answers, call an LLM, start a database or publish the site.

Source licenses and hashes remain in the individual source studies. Do not pool
their denominators into a benchmark or treat NodeSet model declarations as
observations of operating equipment.
