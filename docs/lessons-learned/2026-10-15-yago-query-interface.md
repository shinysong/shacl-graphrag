# 2026-10-15 — YAGO query bindings and validation dead ends

## Context

A 12-episode LLM integration diagnostic reused original YAGO data and SHACL. A separate one-episode scaffolded follow-up preserved the initial outcomes.

## Incident

A constant-subject pattern did not bind projected `?s`. The tool rejected returned bindings with a generic non-source-triple error. Mandatory validation also prevented unknown answers from terminating when evidence was empty. Neither issue establishes defective YAGO ontology or model-independent semantic inability.

Posthoc checks passed for all four original subject contexts. Three source-supported LLM answers had retrieved evidence failing the birthplace class constraint because linked-place type descriptions were omitted. These were coordinator checks, not model-selected checks.

## Lesson

Distinguish missing variable bindings from invented triples in tool feedback. Permit explicit unresolved termination while recording that validation could not execute. A SHACL class violation on retrieved evidence can reflect omitted type context rather than a false source relation.

## Follow-up

- [ ] Add explicit unbound-variable diagnostics under fresh review.
- [ ] Allow evidence-insufficient termination without labeling it a validation pass.
- [ ] Compare a model-selected entity-description tool separately from free SPARQL.
