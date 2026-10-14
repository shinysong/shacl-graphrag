#!/usr/bin/env python3
"""Offline, bounded source descriptions and deliberately lossy projection diagnostics.

No model, network, imported ontology resolution, truth scoring, or graph joins.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import itertools
import json
import shutil
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from xml.parsers import expat

from rdflib import Graph, Namespace
from rdflib.namespace import OWL, RDF, RDFS, XSD

ROOT = Path(__file__).resolve().parents[1]
SH = Namespace('http://www.w3.org/ns/shacl#')


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return {'path': str(path), 'sha256': h.hexdigest(), 'bytes': Path(path).stat().st_size}


def walk(value, path=''):
    """Yield JSON objects with RFC 6901 pointer paths, including list indexes."""
    if isinstance(value, dict):
        yield path, value
        for key, child in value.items():
            yield from walk(child, path + '/' + key.replace('~', '~0').replace('/', '~1'))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, path + '/' + str(index))


def profile_fhir(resources):
    keys = [r['resourceType'] + '/' + r['id'] for r in resources]
    bare = Counter(r['id'] for r in resources)
    references, coding, quantities = [], [], []
    for key, resource in zip(keys, resources):
        for path, obj in walk(resource):
            if 'reference' in obj:
                ref = obj['reference']
                references.append({'source': key, 'path': path + '/reference',
                                   'reference': ref, 'resolved_in_bundle': ref in keys})
            if 'system' in obj and 'code' in obj:
                coding.append({'source': key, 'path': path,
                               **{k: obj[k] for k in ('system', 'code') if k in obj}})
            if path.endswith('/valueQuantity'):
                quantities.append({'source': key, 'path': path,
                                   **{k: obj[k] for k in ('value', 'unit', 'system', 'code') if k in obj}})
    flat = [{'source': r['source'], 'reference': r['reference']} for r in references]
    return ({'resources': len(resources), 'typed_keys': keys,
             'typed_key_unique_count': len(set(keys)), 'bare_id_unique_count': len(bare),
             'bare_id_collision_groups': {k: v for k, v in bare.items() if v > 1},
             'bare_id_overwrite_losses': len(keys) - len(bare),
             'references': len(references),
             'unresolved_in_selected_bundle': sum(not r['resolved_in_bundle'] for r in references),
             'reference_scope': 'Exact relative reference membership in these resources only; unresolved does not imply globally invalid.',
             'deliberate_pathless_projection': {'reference_rows': len(flat),
                 'removed_path_fields': len(references),
                 'interpretation': 'Removing paths loses reference roles such as subject and encounter; no answer-error score.'}},
            {'references': references, 'pathless_references': flat,
             'coding_namespaces': coding, 'value_quantities': quantities})


def profile_wikidata(document, entity_id='Q80'):
    entity = document['entities'][entity_id]
    claims = [(prop, claim) for prop, values in entity['claims'].items() for claim in values]
    ranks = Counter(c.get('rank', '<missing>') for _, c in claims)
    snaks = Counter(c['mainsnak']['snaktype'] for _, c in claims)
    qualifier_count = sum(len(v) for _, c in claims for v in c.get('qualifiers', {}).values())
    reference_count = sum(len(c.get('references', [])) for _, c in claims)
    sample = []
    for prop, c in claims:
        if prop == 'P108':
            sample.append({'property': prop, **{k: c[k] for k in
                ('id', 'rank', 'mainsnak', 'qualifiers', 'qualifiers-order') if k in c},
                'reference_blocks': len(c.get('references', []))})
    return ({'entity': entity_id, 'lastrevid': entity.get('lastrevid'),
             'selection': 'One purposefully selected entity; not representative domain prevalence.',
             'claims': len(claims), 'properties': len(entity['claims']),
             'ranks': dict(ranks), 'mainsnak_types': dict(snaks),
             'qualifier_snaks': qualifier_count, 'reference_blocks': reference_count,
             'qualifier_snaktypes': dict(Counter(s['snaktype'] for _, c in claims
                 for values in c.get('qualifiers', {}).values() for s in values)),
             'reference_snaks': sum(len(values) for _, c in claims
                 for ref in c.get('references', []) for values in ref.get('snaks', {}).values()),
             'reference_snaktypes': dict(Counter(s['snaktype'] for _, c in claims
                 for ref in c.get('references', []) for values in ref.get('snaks', {}).values() for s in values)),
             'claims_with_qualifiers': sum(bool(c.get('qualifiers')) for _, c in claims),
             'claims_with_references': sum(bool(c.get('references')) for _, c in claims),
             'deliberate_subject_property_value_projection': {
                 'policy': 'One row per claim, retaining subject, property and entire mainsnak (including snaktype); no deduplication.',
                 'rows': len(claims), 'removed_rank_fields': sum('rank' in c for _, c in claims),
                 'removed_statement_ids': sum('id' in c for _, c in claims),
                 'removed_qualifier_snaks': qualifier_count,
                 'removed_reference_blocks': reference_count,
                 'interpretation': 'Metadata removal counts, not semantic errors or benchmark outcomes.'}},
            {'entity': entity_id, 'lastrevid': entity.get('lastrevid'), 'employer_P108': sample})


def check_local_xml(raw):
    """Allow FIBO's internal URI entities, but reject external DTDs/entities."""
    parser = expat.ParserCreate()

    def doctype(name, system_id, public_id, internal):
        if system_id or public_id:
            raise ValueError('External XML DTD prohibited')

    def entity(name, parameter, value, base, system_id, public_id, notation):
        if system_id or public_id or parameter:
            raise ValueError('External or parameter XML entity prohibited')

    parser.StartDoctypeDeclHandler = doctype
    parser.EntityDeclHandler = entity
    parser.Parse(raw, True)


def local_rdf(path, fmt):
    raw = Path(path).read_bytes()
    if fmt == 'xml':
        check_local_xml(raw)
    return Graph().parse(data=raw, format=fmt, publicID=Path(path).resolve().as_uri())


def profile_fibo(path):
    graph = local_rdf(path, 'xml')
    count = lambda kind: len(set(graph.subjects(RDF.type, kind)))
    imports = sorted(str(obj) for obj in graph.objects(None, OWL.imports))
    return {'triples': len(graph), 'owl_classes': count(OWL.Class),
            'object_properties': count(OWL.ObjectProperty), 'imports': imports,
            'import_triples': len(imports),
            'deprecated_assertions': len(list(graph.triples((None, OWL.deprecated, None)))),
            'subproperty_triples': len(list(graph.triples((None, RDFS.subPropertyOf, None)))),
            'inverse_triples': len(list(graph.triples((None, OWL.inverseOf, None)))),
            'transitive_properties': count(OWL.TransitiveProperty),
            'scope': 'One asserted RDF/XML module only; imports listed, never fetched or inferred; not a closed ontology.'}


def profile_yago(path):
    graph = local_rdf(path, 'turtle')
    property_nodes = set(graph.objects(None, SH.property)) | set(graph.subjects(RDF.type, SH.PropertyShape))
    dates = [(s, o) for s, o in graph.subject_objects(SH.datatype)
             if o in (XSD.date, XSD.dateTime, XSD.gYear, XSD.gYearMonth)]
    return {'triples': len(graph), 'node_shapes': len(set(graph.subjects(RDF.type, SH.NodeShape))),
            'property_shape_nodes_explicit_or_linked': len(property_nodes),
            'explicit_property_shapes': len(set(graph.subjects(RDF.type, SH.PropertyShape))),
            'date_datatype_constraints': dict(Counter(str(o) for _, o in dates)),
            'scope': 'Original YAGO 4.6 SHACL schema only; no instance benchmark; CC BY 4.0.'}, {
            'date_constraints': sorted([{'path': str(p), 'datatype': str(o)}
                for s, o in dates for p in graph.objects(s, SH.path)], key=lambda x: (x['path'], x['datatype']))}


def read_archive_rows(path, limit=256):
    with zipfile.ZipFile(path) as archive:
        members = [n for n in archive.namelist() if n.lower().endswith('.csv')]
        if len(members) != 1:
            raise ValueError(f'Expected one CSV member, found {len(members)}')
        with archive.open(members[0]) as raw:
            rows = list(itertools.islice(csv.DictReader(io.TextIOWrapper(raw, encoding='utf-8-sig')), limit))
    return members[0], rows


def profile_gleif(rr_rows, repex_rows):
    def counts(rows, field):
        return dict(Counter(row.get(field, '') for row in rows))
    period_fields = sorted({k for row in rr_rows for k in row if k.startswith('Relationship.Period.')})
    selected = ('Relationship.StartNode.NodeID', 'Relationship.StartNode.NodeIDType',
                'Relationship.EndNode.NodeID', 'Relationship.EndNode.NodeIDType',
                'Relationship.RelationshipType', 'Relationship.RelationshipStatus', 'Registration.RegistrationStatus')
    return {'rr_rows': len(rr_rows), 'repex_rows': len(repex_rows),
            'selection': 'First 256 rows per archive in CSV order; bounded biased convenience sample.',
            'relationship_types': counts(rr_rows, 'Relationship.RelationshipType'),
            'relationship_status': counts(rr_rows, 'Relationship.RelationshipStatus'),
            'registration_status': counts(rr_rows, 'Registration.RegistrationStatus'),
            'period_field_nonempty_counts': {k: sum(bool(r.get(k)) for r in rr_rows) for k in period_fields},
            'period_types': dict(Counter(v for r in rr_rows for k, v in r.items()
                if k.startswith('Relationship.Period.') and k.endswith('.periodType') and v)),
            'exception_categories': counts(repex_rows, 'Exception.Category'),
            'exception_reasons': dict(Counter(v for r in repex_rows for k, v in r.items()
                if k.startswith('Exception.Reason.') and v)),
            'scope': 'No joins or parent-absence inference. No edge in this sample does not mean no parent.'}, {
            'rr_first_three': [{k: r[k] for k in (*selected, *period_fields) if k in r} for r in rr_rows[:3]],
            'repex_first_three': [{k: v for k, v in r.items() if k == 'LEI' or k.startswith('Exception.')} for r in repex_rows[:3]]}


class Headings(HTMLParser):
    def __init__(self):
        super().__init__()
        self.counts = Counter()

    def handle_starttag(self, tag, attrs):
        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self.counts[tag] += 1


def profile_documents(html_path, xsd_path):
    html = Path(html_path).read_bytes()
    parser = Headings()
    parser.feed(html.decode('utf-8'))
    raw = Path(xsd_path).read_bytes()
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('External XML declarations prohibited')
    root = ET.fromstring(raw)
    ns = {'xs': 'http://www.w3.org/2001/XMLSchema'}
    fields = [{'name': e.attrib['name'], 'type': e.attrib.get('type')}
              for e in root.findall('.//xs:element', ns)
              if e.attrib.get('name') in ('LegalAddress', 'HeadquartersAddress')]
    return {'html_heading_counts': dict(parser.counts), 'html_content_sha256': hashlib.sha256(html).hexdigest(),
            'xsd_address_elements': fields,
            'scope': 'Structural document description; address purpose requires manual official-definition interpretation. No automatic semantic interpretation or long copied definitions.'}


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n')


def run(output, root=ROOT):
    output.mkdir(parents=True, exist_ok=False)
    summary = {'protocol': 'domain-characteristics-1', 'created_at': datetime.now(UTC).isoformat(),
               'status': 'running', 'scope': 'Offline descriptive source characterization and deliberate projection diagnostics; not a benchmark, prevalence estimate, or semantic-error score.',
               'provenance': {}, 'profiles': {}, 'failures': []}
    samples = {}
    base = root / '_workspace/domain-characteristics'
    paths = {name: base / name for name in ('download-manifest.json', 'fhir-observation.json',
        'fhir-patient.json', 'fhir-encounter.json', 'fibo-relations.rdf', 'fibo-license.txt', 'wikidata-Q80.json')}
    paths.update({name: root / 'data/gleif/20261012T080000' / name for name in ('rr.csv.zip', 'repex.csv.zip', 'manifest.json')})
    paths['yago-schema'] = root / 'data/yago/4.6/schema.ttl'
    paths.update({name: root / '_workspace/bounded-refresh' / name for name in
                  ('gleif-format.html', 'lei-cdf-3.1.xsd', 'official-doc-manifest.json')})
    paths['code'] = Path(__file__).resolve()
    paths['tests'] = root / 'tests/test_domain_sources.py'
    try:
        (output / 'source').mkdir()
        (output / 'provenance').mkdir()
        for name in ('code', 'tests'):
            source = paths[name]
            archived = output / 'source' / source.name
            shutil.copyfile(source, archived)
            summary['provenance'][name] = digest(archived)
        for name, path in paths.items():
            summary['provenance'][name] = digest(path)
            if name in ('download-manifest.json', 'official-doc-manifest.json', 'manifest.json'):
                archived_name = 'gleif-manifest.json' if name == 'manifest.json' else name
                shutil.copyfile(path, output / 'provenance' / archived_name)
        manifest = json.loads(paths['download-manifest.json'].read_text())
        summary['source_download_manifest'] = manifest
        summary['official_document_manifest'] = json.loads(paths['official-doc-manifest.json'].read_text())
        gleif_manifest = json.loads(paths['manifest.json'].read_text())
        summary['gleif_source_manifest'] = gleif_manifest
        for name in ('rr', 'repex'):
            actual = summary['provenance'][name + '.csv.zip']
            frozen = gleif_manifest['files'][name]
            if actual['sha256'] != frozen['sha256'] or actual['bytes'] != frozen['size']:
                raise ValueError('Frozen GLEIF archive differs: ' + name)
        summary['gleif_verified_archives'] = {
            'release': gleif_manifest['publish_date'], 'archives': ['rr', 'repex'],
            'checks': 'Full archive SHA-256 and byte length match the retained same-release manifest; LEI archive not read or verified.'}
        for entry in manifest:
            actual = summary['provenance'][entry['path']]
            if actual['sha256'] != entry['sha256'] or actual['bytes'] != entry['bytes']:
                raise ValueError('Frozen download differs: ' + entry['path'])
        jobs = {
            'fhir': lambda: profile_fhir([json.loads(paths[n].read_text()) for n in
                                         ('fhir-observation.json', 'fhir-patient.json', 'fhir-encounter.json')]),
            'fibo': lambda: (profile_fibo(paths['fibo-relations.rdf']), {}),
            'wikidata': lambda: profile_wikidata(json.loads(paths['wikidata-Q80.json'].read_text())),
            'yago': lambda: profile_yago(paths['yago-schema']),
            'documents': lambda: (profile_documents(paths['gleif-format.html'], paths['lei-cdf-3.1.xsd']), {}),
        }
        def gleif():
            rr_member, rr = read_archive_rows(paths['rr.csv.zip'])
            re_member, re = read_archive_rows(paths['repex.csv.zip'])
            result, sample = profile_gleif(rr, re)
            result['archive_members'] = {'rr': rr_member, 'repex': re_member}
            return result, sample
        jobs['gleif'] = gleif
        for name, job in jobs.items():
            try:
                summary['profiles'][name], samples[name] = job()
            except Exception as exc:  # noqa: BLE001 - retain failed provenance/profile attempts
                summary['failures'].append({'stage': name, 'type': type(exc).__name__, 'message': str(exc)})
            save(output / 'summary.json', summary)
            save(output / 'samples.json', samples)
    except Exception as exc:  # noqa: BLE001 - retain failed provenance/profile attempts
        summary['failures'].append({'stage': 'provenance', 'type': type(exc).__name__, 'message': str(exc)})
    finally:
        summary['status'] = 'partial_failed' if summary['failures'] else 'complete'
        save(output / 'summary.json', summary)
        save(output / 'samples.json', samples)
    return 1 if summary['failures'] else 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New directory; never overwrite previous results')
    args = parser.parse_args()
    raise SystemExit(run(args.output))
