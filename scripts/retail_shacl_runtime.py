"""Copy installed distributions only; run fixed authored pySHACL checks in container."""
import hashlib
from importlib import metadata
import json
from pathlib import Path
import shutil
import sysconfig
from packaging.requirements import Requirement
from scripts.retail_python_runner import execute

BASE = Path('_workspace/retail-llm-v1/shacl-runtime-v1')
PROBE = b'''def evaluate(packet):
    import importlib.metadata
    import rdflib
    from pyshacl import validate
    shape = """@prefix sh: <http://www.w3.org/ns/shacl#> .
    @prefix ex: <urn:probe:> .
    ex:shape a sh:NodeShape; sh:targetNode ex:row;
      sh:property [sh:path ex:value; sh:minInclusive 0]."""
    results = {}
    for name, value in (("positive", 1), ("negative", -1)):
        data = rdflib.Graph()
        data.add((rdflib.URIRef("urn:probe:row"), rdflib.URIRef("urn:probe:value"), rdflib.Literal(value)))
        conforms, report, text = validate(data, shacl_graph=rdflib.Graph().parse(data=shape, format="turtle"),
                                         inference="none", advanced=False, js=False, do_owl_imports=False)
        results[name] = {"conforms": bool(conforms), "report_turtle": report.serialize(format="turtle")}
    return {"versions": {name: importlib.metadata.version(name) for name in ("pyshacl", "rdflib")},
            "results": results}
'''


def main():
    BASE.mkdir(parents=True, exist_ok=False)
    site = BASE/'site'
    site.mkdir()
    installed_site = Path(sysconfig.get_paths()['purelib']).resolve()
    pending = ['pyshacl']
    seen = set()
    versions = {}
    while pending:
        name = pending.pop()
        dist = metadata.distribution(name)
        canonical = dist.metadata['Name'].lower().replace('_', '-')
        if canonical in seen:
            continue
        seen.add(canonical)
        versions[canonical] = dist.version
        for dependency in dist.requires or []:
            req = Requirement(dependency)
            if req.marker is None or req.marker.evaluate({'extra': ''}):
                if req.specifier and metadata.version(req.name) not in req.specifier:
                    raise ValueError('Installed dependency version mismatch')
                pending.append(req.name)
        for entry in dist.files or []:
            original = Path(dist.locate_file(entry)).resolve()
            # Console entry points outside site-packages are not needed or copied.
            if not original.is_relative_to(installed_site):
                continue
            if original.suffix == '.pyc' or not original.is_file():
                continue
            relative = original.relative_to(installed_site)
            destination = site/relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, destination)
    hashes = {str(p.relative_to(site)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in site.rglob('*') if p.is_file()}
    (BASE/'hashes.json').write_text(json.dumps(hashes, indent=2))
    (BASE/'versions.json').write_text(json.dumps(versions, indent=2))
    result = execute(PROBE, {}, BASE/'authored-check', shacl_dependencies=True)
    (BASE/'execution-summary.json').write_text(json.dumps(result, indent=2))
    assert result['container_absent'], 'Owned container cleanup unresolved'
    assert result['status'] == 'completed', result['status']
    output = json.loads((BASE/'authored-check/stdout.bin').read_text())
    (BASE/'validation-results.json').write_text(json.dumps(output, indent=2))
    assert output['results']['positive']['conforms'] is True
    assert output['results']['negative']['conforms'] is False
    print(json.dumps({'versions': output['versions'],
                      'positive_conforms': output['results']['positive']['conforms'],
                      'negative_conforms': output['results']['negative']['conforms'],
                      'container_absent': result['container_absent']}))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        if BASE.exists():
            with (BASE/'failure.json').open('x') as f:
                json.dump({'error_type': type(exc).__name__}, f)
        raise
