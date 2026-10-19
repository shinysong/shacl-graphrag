"""Offline, authored evaluator controls; never reads model outputs or repairs gold."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys

from rdflib import Graph
from pyshacl import validate

PREFIX = '''@prefix ex: <urn:audit:> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
'''
STRICT = PREFIX + '''ex:Rule a sh:NodeShape ; sh:targetClass ex:Book ;
 sh:property [ sh:path ex:author ; sh:minCount 1 ; sh:maxCount 1 ] .
'''
SHAPES = {
    'self': STRICT,
    'weaker': STRICT.replace('sh:minCount 1', 'sh:minCount 0').replace('sh:maxCount 1', 'sh:maxCount 2'),
    'missing_target': STRICT.replace('sh:targetClass ex:Book ;', ''),
    'wrong_path': STRICT.replace('sh:path ex:author', 'sh:path ex:editor'),
}
DATA = {
    'zero_authors': PREFIX + 'ex:book a ex:Book .',
    'one_author': PREFIX + 'ex:book a ex:Book ; ex:author ex:alice .',
    'two_authors': PREFIX + 'ex:book a ex:Book ; ex:author ex:alice, ex:bob .',
    'untargeted': PREFIX + 'ex:other a ex:Other .',
}
EXPECTED = {
    'self': [False, True, False, True],
    'weaker': [True, True, True, True],
    'missing_target': [True, True, True, True],
    'wrong_path': [False, False, False, True],
}


def run(upstream, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    upstream = Path(upstream).resolve()
    sys.path.insert(0, str(upstream))
    import evaluators
    result = {
        'scope': 'Authored offline controls, not new LLM measurements or logical-equivalence proof.',
        'versions': {p: importlib.metadata.version(p) for p in ['rdflib', 'pyshacl', 'rdf-graph-gen', 'setuptools']},
        'upstream_sha256': hashlib.sha256((upstream / 'evaluators.py').read_bytes()).hexdigest(),
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'shape_ttl': SHAPES, 'data_ttl': DATA, 'expected': EXPECTED,
        'witness_results': {}, 'upstream_sample_results': {},
    }
    for name, shape in SHAPES.items():
        vector = []
        for data in DATA.values():
            conforms, _, _ = validate(Graph().parse(data=data, format='turtle'),
                                      shacl_graph=Graph().parse(data=shape, format='turtle'))
            vector.append(bool(conforms))
        result['witness_results'][name] = vector
        result['upstream_sample_results'][name] = evaluators.evaluate_semantic_graph_equivalence(
            STRICT, shape, record_id=name, subset='authored-controls', model='offline',
            output_dir=str(output), scale=10, batch_size=100)
    invalid = PREFIX + 'ex:Rule a sh:NodeShape ; sh:property [ sh:path ex:author ; sh:minCount "one" ] .'
    result['invalid_shape_ttl'] = invalid
    result['upstream_invalid_shape_check'] = evaluators.validate_llm_shacl(invalid)
    try:
        conforms, _, report = validate(Graph(), shacl_graph=Graph().parse(data=invalid, format='turtle'),
                                      meta_shacl=True, do_owl_imports=False)
        result['explicit_meta_check'] = {'status': 'returned', 'conforms': bool(conforms), 'report': report}
    except Exception as exc:
        result['explicit_meta_check'] = {'status': 'exception', 'type': type(exc).__name__, 'message': str(exc)}
    result['witness_expectations_match'] = result['witness_results'] == EXPECTED
    result['limits'] = ['Same graph-level conformance on these four data graphs proves no equivalence.',
                       'Generated reference-only samples may omit discriminating inputs.',
                       'Meta-check exceptions retained, not silently treated as model failures.',
                       'No original dataset, model output, evaluator source or paid ledger modified.']
    (output / 'result.json').write_text(json.dumps(result, indent=2))
    if not result['witness_expectations_match']:
        raise RuntimeError('Authored witness expectations failed; inspect preserved output')
    print(json.dumps({'output': str(output / 'result.json'), 'witness_expectations_match': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--upstream', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    run(args.upstream, args.output)
