"""Declaration-derived, sample-only SHACL diagnostics; never business approval.

Only flat NodeShapes with explicit exported targets, simple property IRIs,
min/maxCount and integer/string/double datatypes are supported. Parsing and
pySHACL run in a disposable, time-bounded process; no imports or inference.
"""
import hashlib
import json
import math
import re
import subprocess
import sys
from urllib.parse import quote

from rdflib import BNode, Graph, Literal, Namespace, RDF, URIRef, XSD

from .workspace_database import DatabaseSourceError

SH = Namespace('http://www.w3.org/ns/shacl#')
VERSION = 'database-declaration-shacl-1'
MAX_BYTES = 262144
MAX_TRIPLES = 4000
MAX_ROWS = 50
TIMEOUT_SECONDS = 8
SCOPE = 'exported_bounded_sample_only_not_full_snapshot_or_business_truth'


def _hash(text):
    return hashlib.sha256(text.encode()).hexdigest()


def _iri(base, *parts):
    return URIRef(base + '/'.join(quote(str(p), safe='') for p in parts))


def propose(draft):
    """Return a JSON artifact from a caller-restored registered database draft.

    Source binding is copied, not independently verified here. Caller must use
    DatabaseWorkspaceAdapter.restore before invoking this pure function.
    """
    if not isinstance(draft, dict) or draft.get('adapter') != 'registered-database-1':
        raise DatabaseSourceError('SHACL drafts require a registered database workspace')
    binding = draft.get('database', {})
    digest = binding.get('snapshot_sha256', '')
    if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
        raise DatabaseSourceError('Invalid database source binding')
    base = 'urn:db-sample:' + digest + ':'
    data, shapes = Graph(), Graph()
    shapes.bind('sh', SH)
    shapes.bind('xsd', XSD)
    mappings, rules, omissions = [], [], []
    count = 0
    sources = draft.get('sources', [])
    if not isinstance(sources, list) or len(sources) > 100:
        raise DatabaseSourceError('Too many database tables')
    for table in sources:
        name = table['name']
        if table.get('sha256') != digest or table.get('source_id') != binding.get('source_id'):
            raise DatabaseSourceError('Mismatched table source binding')
        columns = table.get('columns', [])
        sample = table.get('sample', [])
        if len(columns) > 200 or len(sample) > 20:
            raise DatabaseSourceError('Database sample exceeds declared bounds')
        rows = sample[:max(0, MAX_ROWS-count)]
        targets = [_iri(base, name, 'row', i) for i in range(len(rows))]
        count += len(rows)
        shape = _iri(base, name, 'shape')
        mapping = {'table': name, 'rows': [str(r) for r in targets], 'properties': []}
        mappings.append(mapping)
        if len(rows) < len(sample):
            omissions.append({'table': name, 'reason': 'total_sample_row_limit'})
        if not rows:
            omissions.append({'table': name, 'reason': 'no_exported_targets'})
            continue
        shapes.add((shape, RDF.type, SH.NodeShape))
        for target in targets:
            shapes.add((shape, SH.targetNode, target))
            data.add((target, RDF.type, _iri(base, name, 'Row')))
        for column in columns:
            col = column['name']
            prop = _iri(base, name, 'column', col)
            mapping['properties'].append({'column': col, 'iri': str(prop)})
            if column.get('hidden') == 1:
                omissions.append({'table': name, 'column': col, 'reason': 'hidden_column'})
                continue
            declared = str(column.get('type', '')).strip().upper()
            datatype = {'INTEGER': XSD.integer, 'TEXT': XSD.string, 'REAL': XSD.double}.get(declared)
            if datatype is None:
                omissions.append({'table': name, 'column': col, 'reason': 'flexible_or_unsupported_declared_type', 'declared_type': declared})
            for i, row in enumerate(rows):
                value = row.get(col)
                if value is None:
                    continue
                if type(value) not in (str, int, float) or type(value) is float and not math.isfinite(value):
                    omissions.append({'table': name, 'column': col, 'row_index': i, 'reason': 'unsupported_or_truncated_sample_value'})
                    continue
                # SQLite affinity is not strict typing: preserve mismatching values
                # so actual pySHACL can diagnose rather than silently repair them.
                if datatype == XSD.double and type(value) in (int, float):
                    obj = Literal(float(value), datatype=XSD.double)
                else:
                    obj = Literal(value)
                data.add((targets[i], prop, obj))
            required = column.get('notnull') == 1
            if datatype is not None or required:
                pshape = BNode('p' + _hash(json.dumps([name, col], ensure_ascii=False)))
                shapes.add((shape, SH.property, pshape))
                shapes.add((pshape, SH.path, prop))
                if datatype is not None:
                    shapes.add((pshape, SH.datatype, datatype))
                if required:
                    shapes.add((pshape, SH.minCount, Literal(1)))
                rules.append({'table': name, 'column': col, 'origin': 'sqlite_declaration', 'declared_type': declared, 'datatype': str(datatype) if datatype else None, 'min_count': 1 if required else None})
    if len(shapes) > MAX_TRIPLES or len(data) > MAX_TRIPLES:
        raise DatabaseSourceError('SHACL sample exceeds triple limit; use a smaller source draft')
    st, dt = shapes.serialize(format='turtle'), data.serialize(format='turtle')
    if max(len(st.encode()), len(dt.encode())) > MAX_BYTES:
        raise DatabaseSourceError('SHACL sample exceeds byte limit')
    return {'version': VERSION, 'label': 'DB declaration-derived SHACL draft',
            'source_binding': {k: binding.get(k) for k in ('source_id', 'snapshot_sha256', 'format')},
            'scope': SCOPE, 'shapes_turtle': st, 'sample_data_turtle': dt,
            'sample_sha256': _hash(dt), 'exported_rows': count, 'mappings': mappings,
            'rules': rules, 'omissions': omissions,
            'limits': {'rows': MAX_ROWS, 'bytes_per_graph': MAX_BYTES, 'triples_per_graph': MAX_TRIPLES, 'validation_seconds': TIMEOUT_SECONDS},
            'interpretation': 'Explicit NOT NULL only; no PK/FK cardinality, inferred business rules, model semantics, completeness or approval. Omitted values may produce sample violations.'}


def validate(artifact, edited_turtle):
    """Return a saveable JSON report; neither approve nor mutate anything.

    Errors and timeout are diagnostic statuses, never a conformance decision.
    The caller stores this report separately from draft approval.
    """
    common = {'version': VERSION, 'scope': SCOPE, 'automatic_approval': False}
    if not isinstance(artifact, dict) or artifact.get('version') != VERSION:
        return {**common, 'status': 'rejected', 'reason': 'Unsupported artifact'}
    data = artifact.get('sample_data_turtle')
    if any(not isinstance(x, str) or len(x.encode()) > MAX_BYTES for x in (data, edited_turtle)):
        return {**common, 'status': 'rejected', 'reason': 'Graph text exceeds allowed bounds'}
    common.update(source_binding=artifact.get('source_binding'), sample_sha256=_hash(data), shapes_sha256=_hash(edited_turtle))
    if artifact.get('sample_sha256') != _hash(data):
        return {**common, 'status': 'rejected', 'reason': 'Sample digest mismatch'}
    try:
        run = subprocess.run([sys.executable, '-m', __name__, '--worker'],
                             input=json.dumps({'data': data, 'shapes': edited_turtle}),
                             text=True, capture_output=True, timeout=TIMEOUT_SECONDS, check=False)
        if run.returncode:
            return {**common, 'status': 'error', 'reason': 'Isolated validation failed'}
        return {**common, **json.loads(run.stdout)}
    except subprocess.TimeoutExpired:
        return {**common, 'status': 'timeout', 'reason': 'Isolated validation exceeded time limit'}
    except (ValueError, OSError):
        return {**common, 'status': 'error', 'reason': 'Isolated validation unavailable'}


def _check(data, shapes):
    if len(data) > MAX_TRIPLES or len(shapes) > MAX_TRIPLES:
        raise ValueError('Graph exceeds triple limit')
    targets = set(data.subjects())
    if len(targets) > MAX_ROWS:
        raise ValueError('Too many exported targets')
    for s, p, o in data:
        if not isinstance(s, URIRef) or not isinstance(p, URIRef) or not (isinstance(o, Literal) or p == RDF.type and isinstance(o, URIRef)):
            raise ValueError('Unsupported sample RDF structure')
    roots = set(shapes.subjects(RDF.type, SH.NodeShape))
    properties = set(shapes.objects(None, SH.property))
    if not roots or not properties:
        raise ValueError('At least one explicit shape and property constraint required')
    if roots & properties or any(not isinstance(p, BNode) for p in properties):
        raise ValueError('Only flat blank-node property shapes supported')
    for s, p, o in shapes:
        if s in roots:
            ok = (p == RDF.type and o == SH.NodeShape or p == SH.targetNode and o in targets or p == SH.property and o in properties)
        elif s in properties:
            ok = (p == SH.path and isinstance(o, URIRef) or p == SH.datatype and o in (XSD.integer, XSD.string, XSD.double) or p in (SH.minCount, SH.maxCount) and isinstance(o, Literal) and o.datatype == XSD.integer and type(o.toPython()) is int and 0 <= o.toPython() <= 50)
        else:
            ok = False
        if not ok:
            raise ValueError('Unsupported SHACL predicate, target or structure')
    for root in roots:
        if not list(shapes.objects(root, SH.targetNode)):
            raise ValueError('Explicit exported target nodes required')
    for prop in properties:
        if len(list(shapes.objects(prop, SH.path))) != 1:
            raise ValueError('Exactly one simple property path required')
        if not (list(shapes.objects(prop, SH.datatype)) or list(shapes.objects(prop, SH.maxCount))
                or any(value.toPython() > 0 for value in shapes.objects(prop, SH.minCount))):
            raise ValueError('A property path or minCount zero alone does not constrain values')
        for predicate in (SH.datatype, SH.minCount, SH.maxCount):
            if len(list(shapes.objects(prop, predicate))) > 1:
                raise ValueError('Duplicate property constraint')
    if shapes and not roots:
        raise ValueError('Explicit NodeShapes required')


def _worker(payload):
    try:
        data, shapes = Graph(), Graph()
        data.parse(data=payload['data'], format='turtle')
        shapes.parse(data=payload['shapes'], format='turtle')
        _check(data, shapes)
    except Exception:
        return {'status': 'rejected', 'reason': 'Malformed RDF or unsupported flat SHACL structure'}
    from pyshacl import validate as run_shacl
    try:
        conforms, report, _ = run_shacl(data, shacl_graph=shapes, inference='none', advanced=False, js=False, do_owl_imports=False, inplace=False)
        results = []
        nodes = list(report.subjects(RDF.type, SH.ValidationResult))
        for result in nodes[:100]:
            results.append({key: [str(o)[:500] for o in report.objects(result, predicate)][:5] for key, predicate in [('focus_nodes', SH.focusNode), ('paths', SH.resultPath), ('messages', SH.resultMessage), ('components', SH.sourceConstraintComponent)]})
        return {'status': 'completed', 'conforms': bool(conforms), 'engine': 'pySHACL',
                'shape_count': len(set(shapes.subjects(RDF.type, SH.NodeShape))),
                'property_shape_count': len(set(shapes.objects(None, SH.property))),
                'target_count': len(set(shapes.objects(None, SH.targetNode))),
                'result_count': len(nodes), 'results': results, 'results_truncated': len(nodes) > 100}
    except Exception:
        return {'status': 'error', 'reason': 'pySHACL could not complete supported diagnostic'}


if __name__ == '__main__':
    # Only the parent process supplies this bounded JSON protocol.
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (6, 6))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    print(json.dumps(_worker(json.loads(sys.stdin.read(MAX_BYTES * 14)))))
