"""Extract a small YAGO 4.6 cohort plus genuine type/subclass/label context."""
import hashlib
import json
from pathlib import Path

from rdflib import RDF, RDFS, SH, Graph, Namespace

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/yago/4.6'
OUT = ROOT / 'experiments/yago'
SC = Namespace('http://schema.org/')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((RAW / 'manifest.json').read_text())
    for kind in ('schema', 'tiny'):
        if sha(RAW / f'{kind}.ttl') != manifest['files'][kind]['turtle_sha256']:
            raise ValueError('Input hash mismatch')
    prefixes, candidates, taxonomy_lines = [], {}, []
    # The official distribution emits instance facts as one tab-separated Turtle
    # statement per line. Parse all selected statements with RDFLib, not ad hoc literals.
    with (RAW / 'tiny.ttl').open() as stream:
        for line in stream:
            if line.startswith('@prefix '):
                prefixes.append(line)
            parts = line.split('\t', 2)
            if len(parts) != 3:
                continue
            subject, predicate, _ = parts
            if predicate == 'rdfs:subClassOf':
                taxonomy_lines.append(line)
            if predicate == 'schema:birthPlace' and (subject in candidates or len(candidates) < 30):
                candidates.setdefault(subject, []).append(line)
    prefix = ''.join(prefixes)
    places = set()
    for lines in candidates.values():
        for _, _, place in Graph().parse(data=prefix + ''.join(lines), format='turtle'):
            places.add(str(place).replace('http://yago-knowledge.org/resource/', 'yago:'))
    selected = set(candidates) | places
    instance_lines = []
    properties = {'rdf:type', 'rdfs:label', 'schema:birthDate', 'schema:birthPlace'}
    with (RAW / 'tiny.ttl').open() as stream:
        for line in stream:
            parts = line.split('\t', 2)
            # Places contribute only validation context, not unrelated facts.
            if (len(parts) == 3 and parts[0] in selected and parts[1] in properties
                    and (parts[0] in candidates or parts[1] in {'rdf:type', 'rdfs:label'})):
                instance_lines.append(line)
    pool = Graph().parse(data=prefix + ''.join(instance_lines), format='turtle')
    schema = Graph().parse(RAW / 'schema.ttl')
    taxonomy = Graph().parse(data=prefix + ''.join(taxonomy_lines), format='turtle')
    for triple in schema.triples((None, RDFS.subClassOf, None)):
        taxonomy.add(triple)
    for cls in set(taxonomy.subjects(RDFS.subClassOf)) | set(taxonomy.objects(None, RDFS.subClassOf)):
        taxonomy.add((cls, RDF.type, RDFS.Class))
    cohort = []
    for curie in candidates:
        subject = Namespace('http://yago-knowledge.org/resource/')[curie.removeprefix('yago:')]
        parents = list(pool.objects(subject, SC.birthPlace))
        dates = list(pool.objects(subject, SC.birthDate))
        labels = list(pool.objects(subject, RDFS.label))
        if len(parents) != 1 or len(dates) != 1 or not labels:
            continue
        if not list(pool.objects(parents[0], RDFS.label)) or not list(pool.objects(parents[0], RDF.type)):
            continue
        def has_class(node, target):
            return any(t == target or target in taxonomy.transitive_objects(t, RDFS.subClassOf)
                       for t in pool.objects(node, RDF.type))
        if not has_class(subject, SC.Person) or not has_class(parents[0], SC.Place):
            continue
        cohort.append({'subject': str(subject), 'place': str(parents[0]), 'birth_date': dates[0].n3(),
                       'name': str(next((l for l in labels if l.language == 'en'), labels[0])),
                       'split': 'development' if not cohort else 'pilot'})
        if len(cohort) == 4:
            break
    if len(cohort) != 4:
        raise ValueError('Insufficient eligible subjects')
    nodes = {x['subject'] for x in cohort} | {x['place'] for x in cohort}
    from rdflib import URIRef
    data = Graph()
    for node in map(URIRef, nodes):
        for triple in pool.triples((node, None, None)):
            data.add(triple)
    classes = set(data.objects(None, RDF.type))
    closure = Graph()
    for cls in list(classes):
        classes.update(taxonomy.transitive_objects(cls, RDFS.subClassOf))
    for cls in classes:
        for triple in taxonomy.triples((cls, None, None)):
            closure.add(triple)
    for g in (data, closure):
        g.bind('schema', SC)
        g.bind('yago', Namespace('http://yago-knowledge.org/resource/'))
    OUT.mkdir(exist_ok=True)
    data.serialize(OUT / 'data.ttl', format='turtle')
    closure.serialize(OUT / 'taxonomy.ttl', format='turtle')
    # Byte-identical official schema, no added minCount/target/range rules.
    (OUT / 'schema.ttl').write_bytes((RAW / 'schema.ttl').read_bytes())
    record = {'source': manifest, 'selection': 'First four eligible subjects in official tiny birthPlace discovery order; first development, three pilot; no representative sampling claim.',
              'cohort': cohort, 'data_triples': len(data), 'taxonomy_triples': len(closure),
              'schema_triples': len(schema), 'schema_node_shapes': len(set(schema.subjects(RDF.type, SH.NodeShape))),
              'sha256': {name: sha(OUT / name) for name in ('data.ttl', 'taxonomy.ttl', 'schema.ttl')}}
    (OUT / 'manifest.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k:v for k,v in record.items() if k != 'source'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
