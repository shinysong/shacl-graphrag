"""Resident RDFLib/OWL-RL membership and actual SHACL operand validation."""
import json
from urllib.parse import quote
from pathlib import Path
from time import perf_counter_ns
from rdflib import Graph, Namespace, URIRef, Literal, RDF, OWL
from owlrl import DeductiveClosure, OWLRL_Semantics
from pyshacl import validate
from technology_selection_common import normalize, assemble, updated_packet, base
EX = Namespace('urn:selection:')
SH = Namespace('http://www.w3.org/ns/shacl#')
SHAPES = Path(__file__).resolve().parents[1] / 'research/technology-selection/receipt-shapes-v1.ttl'


def node(pair):
    return URIRef('urn:selection:item:' + quote(json.dumps(pair, ensure_ascii=True), safe=''))


class RDFArm:
    def __init__(self, packet):
        start = perf_counter_ns(); self.state = normalize(packet)
        self.normalization_ns = perf_counter_ns()-start
        start = perf_counter_ns()
        self.shapes = Graph().parse(SHAPES, format='turtle')
        self._load()
        self.setup_ns = perf_counter_ns()-start

    def _load(self):
        self.values = Graph(); self.check_ids = {}
        for check in self.state['checks']:
            if check['values'] is None:
                continue
            focus = URIRef('urn:selection:check:' + quote(check['rule_id'], safe=''))
            self.check_ids[focus] = check['rule_id']
            self.values.add((focus, RDF.type, EX[check['kind']]))
            for field, value in zip(('a', 'b', 'c'), check['values']):
                self.values.add((focus, EX[field], Literal(value)))
        # Rebuild from asserted edges, never retain stale inferred triples.
        self.graph = Graph()
        self.graph.add((EX.reaches, RDF.type, OWL.TransitiveProperty))
        for source, edges in self.state['adjacency'].items():
            for _, target in edges:
                self.graph.add((node(source), EX.reaches, node(target)))
        DeductiveClosure(OWLRL_Semantics).expand(self.graph)

    def query(self):
        conforms, report, _ = validate(self.values, shacl_graph=self.shapes, inference='none', advanced=False)
        failed = set()
        for focus in report.objects(None, SH.focusNode):
            if focus not in self.check_ids:
                raise ValueError('unexpected SHACL focus')
            failed.add(self.check_ids[focus])
        if bool(conforms) != (not failed):
            raise ValueError('SHACL report disagreement')
        target = node(self.state['target'])
        members = {(p['id'], p['revision']) for p in self.state['packet']['tables']['product']
                   if (p['id'], p['revision']) != self.state['target'] and
                   (target, EX.reaches, node((p['id'], p['revision']))) in self.graph}
        paths = base.shortest_paths(self.state['adjacency'], self.state['target'])
        return assemble(self.state, failed, members, paths)

    def update(self, command):
        start = perf_counter_ns(); p, changed = updated_packet(self.state, command)
        self.state = normalize(p); normalization_ns = perf_counter_ns()-start
        start = perf_counter_ns(); self._load()
        return dict(changed_occurrences=changed, normalization_ns=normalization_ns,
                    arm_apply_ns=perf_counter_ns()-start, invalidation='full common normalization; asserted graph rebuild and fresh OWL-RL closure for both updates; parsed shapes reused')
