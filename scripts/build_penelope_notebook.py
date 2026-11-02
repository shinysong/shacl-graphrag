"""Build a standalone consumed-source SHACL walkthrough, without campaign execution."""
import argparse
import hashlib
import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import nbformat as nbf
from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpecManager
from nbclient import NotebookClient
from rdflib import RDF, Graph, Literal, Namespace, URIRef

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'research/actionable-evidence-1/source-validation/run-001'
COPY = RUN.parent / 'notebook-copy.ko.json'
DEFAULT = ROOT / 'docs/experiments/seminar/notebooks/penelope-source-validation.ipynb'
P = Namespace('https://example.org/penelope/validation/')
SELECTED = ('PP3:2', 'PP5:25')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def selected_graph(graph):
    roots = []
    for key in SELECTED:
        matches = list(graph.subjects(P.annotationId, Literal(key)))
        if len(matches) != 1:
            raise ValueError(f'Expected one subject for {key}, found {len(matches)}')
        roots.append(matches[0])
    result = Graph()
    for prefix, namespace in graph.namespaces():
        result.bind(prefix, namespace)
    pending, seen = list(roots), set()
    while pending:
        subject = pending.pop()
        if subject in seen:
            continue
        if (subject, RDF.type, P.Annotation) in graph and subject not in roots:
            raise ValueError('Selection reached an unselected annotation')
        seen.add(subject)
        for triple in graph.triples((subject, None, None)):
            result.add(triple)
            if isinstance(triple[2], URIRef) and triple[2] not in seen:
                pending.append(triple[2])
    if set(result.subjects(RDF.type, P.Annotation)) != set(roots):
        raise ValueError('Selection must contain exactly two annotation subjects')
    return result


def build(output, execute=False):
    output = output.resolve()
    receipt_path = output.with_suffix('.execution.json')
    for path in (output, receipt_path, output.with_suffix('.failed.ipynb')):
        if path.exists():
            raise FileExistsError(f'Refusing to overwrite {path}; choose a new --output')
    copy = json.loads(COPY.read_text())
    manifest = json.loads((RUN / 'manifest.json').read_text())
    for name, expected in manifest['hashes'].items():
        if sha((RUN / name).read_bytes()) != expected:
            raise ValueError(f'Frozen input hash mismatch: {name}')
    source = json.loads((RUN / 'input.json').read_text())
    graph = selected_graph(Graph().parse(RUN / 'data.ttl', format='turtle'))
    data_text = graph.serialize(format='turtle')
    shape_text = (RUN / 'shapes.ttl').read_text()
    input_hashes = {name: sha((RUN / name).read_bytes()) for name in
                    ('input.json', 'data.ttl', 'shapes.ttl', 'manifest.json', 'requests.json')}
    provenance = {
        'source_attribution': source['source_attribution'],
        'frozen_run': str(RUN.relative_to(ROOT)),
        'selected_annotation_ids': list(SELECTED),
        'input_sha256': input_hashes,
        'selected_rdf_sha256': sha(data_text.encode()),
        'selection': 'Two annotation subjects and transitively outgoing URI subjects only',
        'namespaces': {'schema': str(P), 'source': 'https://example.org/penelope/source/',
                       'codebook': 'https://example.org/penelope/source/codebook/'},
    }
    requests = [r for r in json.loads((RUN / 'requests.json').read_text())
                if r['annotation_id'] in SELECTED]
    cells = []

    def md(key):
        cells.append(nbf.v4.new_markdown_cell(copy[key], id=key))

    def code(key, text):
        cells.append(nbf.v4.new_code_cell(text, id=key))

    md('intro')
    md('setup_note')
    code('setup', '''import json
import hashlib
from importlib.metadata import version
from rdflib import Graph, Namespace, RDF, Literal
from pyshacl import validate

P = Namespace("https://example.org/penelope/validation/")
SH = Namespace("http://www.w3.org/ns/shacl#")
for package in ("rdflib", "pyshacl"):
    print(package, version(package))''')
    md('provenance_note')
    code('provenance', 'PROVENANCE = ' + repr(provenance) + '\nprint(json.dumps(PROVENANCE, ensure_ascii=False, indent=2))')
    md('data_note')
    code('embedded-data', 'DATA_TTL = ' + repr(data_text) + '''
assert hashlib.sha256(DATA_TTL.encode()).hexdigest() == PROVENANCE["selected_rdf_sha256"]
data = Graph().parse(data=DATA_TTL, format="turtle")
print("annotations =", len(set(data.subjects(RDF.type, P.Annotation))))
print("triples =", len(data))
print(DATA_TTL)''')
    code('source-cells', '''fields = ("defect", "welding_setting", "bead", "x_init_mm", "x_end_mm", "sample_init", "sample_end")
for annotation_id in PROVENANCE["selected_annotation_ids"]:
    subject = data.value(predicate=P.annotationId, object=Literal(annotation_id))
    print("\\n", annotation_id)
    print("source:", data.value(subject, P.archiveMember))
    print("sha256:", data.value(subject, P.sourceFileSha256))
    print("sheet / row:", data.value(subject, P.sheet), data.value(subject, P.excelRow))
    for field in fields:
        cell = data.value(subject, P["cell_" + field])
        value = data.value(subject, P[field])
        print(field, "cell=" + str(data.value(cell, P.cellAddress)), "value=" + str(value))
        if field in ("defect", "welding_setting"):
            print("  sourceCode:", data.value(value, P.sourceCode))
            print("  reference path:", data.value(value, P.archiveMember),
                  data.value(value, P.sheet), data.value(value, P.codeCell))
            print("  codebook row:", data.value(value, P.sourceValuesJSON))''')
    md('shape_note')
    code('full-shapes', 'SHAPES_TTL = ' + repr(shape_text) + '''
assert hashlib.sha256(SHAPES_TTL.encode()).hexdigest() == PROVENANCE["input_sha256"]["shapes.ttl"]
shapes = Graph().parse(data=SHAPES_TTL, format="turtle")
print(SHAPES_TTL)''')
    md('validate_note')
    code('validate', '''conforms, report, report_text = validate(
    data_graph=data, shacl_graph=shapes, inference="none", advanced=False,
    inplace=False, abort_on_first=False)
print("conforms =", bool(conforms))
results = sorted(report.subjects(RDF.type, SH.ValidationResult), key=str)
print("validation results =", len(results))
for result in results:
    focus = report.value(result, SH.focusNode)
    print("annotation:", data.value(focus, P.annotationId))
    print("source shape:", report.value(result, SH.sourceShape))
    print("constraint:", report.value(result, SH.sourceConstraintComponent))
    print("message:", report.value(result, SH.resultMessage))''')
    md('report_note')
    code('full-text-report', 'print(report_text)')
    code('full-rdf-report', 'print(report.serialize(format="turtle"))')
    md('request_note')
    code('saved-requests', 'SAVED_REQUESTS = ' + repr(requests) + '\nprint(json.dumps(SAVED_REQUESTS, ensure_ascii=False, indent=2))')
    md('limits')
    notebook = nbf.v4.new_notebook(cells=cells, metadata={
        'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
        'seminar': provenance,
    })
    receipt = {
        'schema_version': 'penelope-notebook-execution-1',
        'input_sha256': input_hashes,
        'builder_sha256': sha(Path(__file__).read_bytes()),
        'copy_sha256': sha(COPY.read_bytes()),
        'selected_rdf_sha256': sha(data_text.encode()),
        'code_sha256': sha('\n\n'.join(c.source for c in cells if c.cell_type == 'code').encode()),
        'selected_annotation_ids': list(SELECTED),
        'total_cells': len(cells),
        'code_cells': sum(c.cell_type == 'code' for c in cells),
        'executed': False,
        'python_executable': sys.executable,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    if execute:
        # Use this uv interpreter, not a potentially unrelated registered python3.
        with tempfile.TemporaryDirectory(prefix='penelope-notebook-') as temp:
            kernel_dir = Path(temp) / 'kernels' / 'python3'
            kernel_dir.mkdir(parents=True)
            (kernel_dir / 'kernel.json').write_text(json.dumps({
                'argv': [sys.executable, '-m', 'ipykernel_launcher', '-f', '{connection_file}'],
                'display_name': 'Python 3', 'language': 'python'}))
            manager = KernelManager(kernel_name='python3', kernel_spec_manager=
                                    KernelSpecManager(kernel_dirs=[str(kernel_dir.parent)]))
            try:
                NotebookClient(notebook, km=manager, timeout=120,
                               resources={'metadata': {'path': temp}}).execute()
            except Exception:
                with output.with_suffix('.failed.ipynb').open('x') as handle:
                    nbf.write(notebook, handle)
                raise
        receipt['executed'] = True
    receipt['executed_code_cells'] = sum(
        c.cell_type == 'code' and c.execution_count is not None for c in notebook.cells)
    receipt['created_at_utc'] = datetime.now(UTC).isoformat()
    nbf.validate(notebook)
    with output.open('x') as handle:
        nbf.write(notebook, handle)
    receipt['notebook_sha256'] = sha(output.read_bytes())
    with receipt_path.open('x') as handle:
        json.dump(receipt, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    print(json.dumps({'notebook': str(output), 'receipt': str(receipt_path), **receipt}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    build(args.output, args.execute)
