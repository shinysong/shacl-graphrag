# YAGO 4.6 attribution

Source: [YAGO 4.6](https://yago-knowledge.org/downloads/yago-4-6), YAGO team, Télécom Paris.

Data and schema are licensed under [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/).

Citation: Fabian M. Suchanek, Thomas Bonald, Nikola Dobricic, Marc Jeanmougin, Margherita Necchi. *YAGO 4.6: A Logically Consistent Subset of Wikidata*. ISWC 2026 demo paper.

- `schema.ttl`: byte-identical official schema extracted from `yago-4.6-schema.zip`.
- `data.ttl`: selected birthPlace, birthDate, type and label triples from the official `yago-4.6-tiny.zip`. Not the complete distribution.
- `taxonomy.ttl`: selected original subclass paths plus explicit `rdf:type rdfs:Class` declarations for subclass endpoints (RDFS structural entailments, not new domain constraints).
- Injected errors exist only in case/run copies, not in this source subset. See `manifest.json` for URLs, hashes and selection.
