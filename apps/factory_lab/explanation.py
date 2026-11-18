"""Inspectable engine outputs; separate from frozen research review implementations.

No model calls or source lookups. A trace is provenance, not an accuracy score.
"""
from hashlib import sha256

from rdflib import Graph, RDF, RDFS, URIRef
from rdflib.compare import to_canonical_graph
from pyshacl import validate
from owlrl import DeductiveClosure, OWLRL_Semantics

from .review import EX, SH, SHAPES, candidates, rdf_input, python_flags


def canonical(graph):
    return '\n'.join(sorted(' '.join(t.n3() for t in triple) + ' .'
                            for triple in to_canonical_graph(graph))) + '\n'


def term(value):
    return value.n3() if value is not None else None


def shacl_trace(evidence, shapes_text=SHAPES):
    """Validate only supplied evidence; shapes_text is a developer/test argument."""
    rows = candidates(evidence)
    data = rdf_input(rows)
    shapes = Graph().parse(data=shapes_text, format='turtle')
    trace = {
        'engine': 'pySHACL', 'inference': 'none',
        'assessment': 'not_assessed' if not rows else 'selected_candidates_checked',
        'selected_candidates': rows,
        'evidence': [{'tool': e.get('source_tool', e.get('tool')),
                      'arguments': e.get('arguments'), 'snapshot': e.get('snapshot'),
                      'source_sha256': e.get('source_sha256'), 'as_of': e.get('as_of')}
                     for e in evidence],
        'data_turtle': data.serialize(format='turtle'),
        'data_sha256': sha256(canonical(data).encode()).hexdigest(),
        'shapes_turtle': shapes_text,
        'shapes_sha256': sha256(shapes_text.encode()).hexdigest(),
        'checks': [], 'raw_report_turtle': None, 'conforms': None,
        'scope': 'Selected evidence only. Missing records do not identify source absence versus retrieval omission. Conformance does not certify truth, completeness or physical approval.',
        'path_notice': 'Native SPARQL constraints may emit no resultPath or value. Null fields are preserved, not invented.',
    }
    if not rows:
        trace['reason'] = 'No replacement-candidate targets in selected evidence; validation not run.'
        return trace
    conforms, report, text = validate(data, shacl_graph=shapes, advanced=True, inference='none')
    if not isinstance(report, Graph):
        raise RuntimeError('SHACL did not return a report graph')
    trace.update(conforms=bool(conforms), raw_report_turtle=report.serialize(format='turtle'),
                 raw_report_text=text)
    results = []
    for n in report.subjects(RDF.type, SH.ValidationResult):
        focus = report.value(n, SH.focusNode)
        results.append({'focus_node': term(focus), 'candidate': str(data.value(focus, EX.key)),
                        'source_shape': term(report.value(n, SH.sourceShape)),
                        'constraint_component': term(report.value(n, SH.sourceConstraintComponent)),
                        'property_path': term(report.value(n, SH.resultPath)),
                        'value': term(report.value(n, SH.value)),
                        'message': str(report.value(n, SH.resultMessage))})
    trace['results'] = sorted(results, key=lambda r: (r['candidate'], r['message']))
    # The original shapes all target Candidate; do not generalize to arbitrary targets.
    for shape in sorted(shapes.subjects(SH.targetClass, EX.Candidate), key=str):
        constraints = []
        for c in shapes.objects(shape, SH.sparql):
            constraints.append({'message': str(shapes.value(c, SH.message)),
                                'select': str(shapes.value(c, SH.select))})
        for focus in sorted(data.subjects(RDF.type, EX.Candidate), key=str):
            violations = [r for r in results if r['focus_node'] == term(focus)
                          and r['source_shape'] == term(shape)]
            trace['checks'].append({'shape': term(shape), 'focus_node': term(focus),
                                    'candidate': str(data.value(focus, EX.key)),
                                    'constraints': constraints,
                                    'status': 'violation' if violations else 'pass',
                                    'results': violations})
    trace['same_policy_python_flags'] = python_flags(rows)
    return trace


def owl_trace(asserted_text, ontology_text):
    """Actual OWL-RL closure; reconstructed witnesses only for direct subclass typing."""
    asserted = Graph().parse(data=asserted_text, format='turtle')
    ontology = Graph().parse(data=ontology_text, format='turtle')
    if len(asserted) + len(ontology) > 100:
        raise ValueError('Bounded demo supports at most 100 input triples')
    original = set(asserted) | set(ontology)
    closure = Graph()
    for triple in original:
        closure.add(triple)
    DeductiveClosure(OWLRL_Semantics, axiomatic_triples=False, datatype_axioms=False).expand(closure)
    added = Graph()
    for triple in set(closure) - original:
        added.add(triple)
    witnesses = []
    for subject, _, child in asserted.triples((None, RDF.type, None)):
        for parent in ontology.objects(child, RDFS.subClassOf):
            conclusion = (subject, RDF.type, parent)
            if conclusion in added and isinstance(parent, URIRef):
                witnesses.append({'conclusion': [term(x) for x in conclusion],
                                  'premise': [term(x) for x in (subject, RDF.type, child)],
                                  'axiom': [term(x) for x in (child, RDFS.subClassOf, parent)],
                                  'explanation_kind': 'reconstructed direct subclass witness; not internal reasoner proof trace'})
    return {'engine': 'owlrl OWLRL_Semantics', 'asserted_turtle': asserted_text,
            'ontology_turtle': ontology_text,
            'input_sha256': sha256(canonical(asserted + ontology).encode()).hexdigest(),
            'inferred_ntriples': canonical(added), 'inferred_count': len(added),
            'witnesses': sorted(witnesses, key=lambda w: str(w['conclusion'])),
            'scope': 'Positive OWL-RL closure, not full OWL DL reasoning or industrial approval. Generic closure triples are retained; only direct asserted-type/subclass witnesses are explained. No inferred qualification or schedule eligibility.',
            'proof_trace_available': False}
