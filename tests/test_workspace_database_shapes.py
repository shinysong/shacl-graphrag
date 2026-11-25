"""Offline sample diagnostics, never a business-quality benchmark."""
from copy import deepcopy
import json
import sqlite3

import pytest
from rdflib import Graph, Literal, Namespace, XSD

from apps.factory_lab.workspace_database import SQLiteSources
from apps.factory_lab.workspace_database_adapter import DatabaseWorkspaceAdapter
from apps.factory_lab import workspace_database_shapes as shapes

SH = Namespace('http://www.w3.org/ns/shacl#')


@pytest.fixture
def draft(tmp_path):
    path = tmp_path / 'input.sqlite'
    with sqlite3.connect(path) as con:
        con.execute('CREATE TABLE "odd/table" (id INTEGER PRIMARY KEY, title TEXT NOT NULL, loose NUMERIC, amount REAL, payload BLOB)')
        con.execute('INSERT INTO "odd/table" VALUES (1, "hello", 1, 1.5, ?)', (b'private',))
    registry = SQLiteSources(tmp_path / 'registry')
    return DatabaseWorkspaceAdapter(registry).create(registry.register(path)['source_id'])


def test_declaration_export_and_real_diagnostic(draft):
    original = deepcopy(draft)
    artifact = shapes.propose(draft)
    assert artifact == shapes.propose(draft)
    assert draft == original
    json.dumps(artifact, allow_nan=False)
    assert artifact['source_binding']['snapshot_sha256'] == draft['database']['snapshot_sha256']
    assert artifact['exported_rows'] == 1
    assert 'not_full_snapshot' in artifact['scope']
    assert 'odd%2Ftable' in artifact['mappings'][0]['rows'][0]
    assert any(o['reason'] == 'unsupported_or_truncated_sample_value' for o in artifact['omissions'])
    report = shapes.validate(artifact, artifact['shapes_turtle'])
    assert report['status'] == 'completed' and report['conforms'] is True
    assert report['engine'] == 'pySHACL' and report['automatic_approval'] is False
    graph = Graph().parse(data=artifact['shapes_turtle'], format='turtle')
    title = next(p for p in graph.subjects(SH.datatype, XSD.string))
    graph.add((title, SH.maxCount, Literal(0)))
    report = shapes.validate(artifact, graph.serialize(format='turtle'))
    assert report['status'] == 'completed' and report['conforms'] is False
    assert report['result_count'] == 1
    assert draft == original


def test_nullable_pk_and_flexible_affinity(draft):
    artifact = shapes.propose(draft)
    by_name = {r['column']: r for r in artifact['rules']}
    assert by_name['id']['min_count'] is None  # PK does not imply explicit NOT NULL.
    assert by_name['title']['min_count'] == 1
    assert 'loose' not in by_name and 'payload' not in by_name
    # SQLite accepts a mismatching storage class: preserve it as a violation.
    draft['sources'][0]['sample'][0]['id'] = 'wrong'
    artifact = shapes.propose(draft)
    report = shapes.validate(artifact, artifact['shapes_turtle'])
    assert report['status'] == 'completed' and not report['conforms']


def test_empty_or_unconstrained_shapes_are_not_a_product_pass(draft):
    artifact=shapes.propose(draft)
    assert shapes.validate(artifact,'')['status']=='rejected'
    target=artifact['mappings'][0]['rows'][0]
    text=f'@prefix sh: <http://www.w3.org/ns/shacl#> . <urn:shape> a sh:NodeShape; sh:targetNode <{target}>; sh:property [ sh:path <urn:unconstrained> ] .'
    assert shapes.validate(artifact,text)['status']=='rejected'
    text=text.replace('sh:path <urn:unconstrained>', 'sh:path <urn:unconstrained>; sh:minCount 0')
    assert shapes.validate(artifact,text)['status']=='rejected'


@pytest.mark.parametrize('fragment', [
    'sh:sparql [ sh:select "SELECT * WHERE { SERVICE <https://example.org> { ?s ?p ?o } }" ]',
    'sh:js [ sh:jsFunctionName "attack" ]',
    'sh:rule [ a sh:TripleRule ]',
    '<http://www.w3.org/2002/07/owl#imports> <https://example.org>',
    'sh:property [ sh:path [ sh:inversePath <urn:x> ] ]',
    'sh:node <urn:nested>',
    'sh:targetNode <https://example.org/other>',
])
def test_unsupported_executable_and_nested_shapes_rejected(draft, fragment):
    artifact = shapes.propose(draft)
    target = artifact['mappings'][0]['rows'][0]
    edited = f'@prefix sh: <http://www.w3.org/ns/shacl#> . <urn:s> a sh:NodeShape; sh:targetNode <{target}>; {fragment} .'
    assert shapes.validate(artifact, edited)['status'] == 'rejected'


def test_scope_budget_and_tamper(draft):
    table = draft['sources'][0]
    table['sample'] *= 20
    table['row_count'] = 10000
    draft['sources'] = [dict(table, name=f't{i}') for i in range(4)]
    artifact = shapes.propose(draft)
    assert artifact['exported_rows'] == 50
    assert sum(len(m['rows']) for m in artifact['mappings']) == 50
    assert any(o['reason'] == 'total_sample_row_limit' for o in artifact['omissions'])
    assert shapes.validate(artifact, 'x' * (shapes.MAX_BYTES + 1))['status'] == 'rejected'
    artifact['sample_data_turtle'] += '\n# tamper'
    assert shapes.validate(artifact, artifact['shapes_turtle'])['status'] == 'rejected'


def test_timeout_is_not_conformance(draft, monkeypatch):
    import subprocess
    artifact = shapes.propose(draft)
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired('worker', shapes.TIMEOUT_SECONDS)
    monkeypatch.setattr(shapes.subprocess, 'run', timeout)
    report = shapes.validate(artifact, artifact['shapes_turtle'])
    assert report['status'] == 'timeout' and 'conforms' not in report
