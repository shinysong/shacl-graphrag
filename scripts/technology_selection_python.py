"""Resident indexed/config-driven Python comparison. No scorer access."""
import json
from pathlib import Path
from time import perf_counter_ns
from technology_selection_common import normalize, assemble, updated_packet, base

CONFIG = Path(__file__).resolve().parents[1] / 'research/technology-selection/python-rules-v1.json'


class PythonArm:
    def __init__(self, packet):
        start = perf_counter_ns()
        self.state = normalize(packet)
        self.normalization_ns = perf_counter_ns() - start
        start = perf_counter_ns()
        self.rules = json.loads(CONFIG.read_text())
        self.adjacency = self.state['adjacency']
        self.setup_ns = perf_counter_ns() - start

    def query(self):
        failed = set()
        for check in self.state['checks']:
            v = check['values']
            if v is None:
                continue
            kind, rule = check['kind'], self.rules[check['kind']]
            if kind == 'equal' and rule == 'equal':
                ok = v[0] == v[1]
            elif kind == 'quantity' and rule == 'positive_lte':
                ok = 0 < v[0] <= v[1]
            elif kind in ('inspection-status', 'certificate-status'):
                ok = v[0] == rule
            elif kind == 'interval' and rule == 'start_lte_received_lt_end':
                ok = v[0] <= v[1] < v[2]
            else:
                raise ValueError('unsupported rule configuration')
            if not ok:
                failed.add(check['rule_id'])
        paths = base.shortest_paths(self.adjacency, self.state['target'])
        return assemble(self.state, failed, set(paths), paths)

    def update(self, command):
        start = perf_counter_ns()
        p, changed = updated_packet(self.state, command)
        self.state = normalize(p)
        normalization_ns = perf_counter_ns() - start
        start = perf_counter_ns()
        self.adjacency = self.state['adjacency']
        return dict(changed_occurrences=changed, normalization_ns=normalization_ns,
                    arm_apply_ns=perf_counter_ns() - start,
                    invalidation='full common normalization and adjacency rebuild; no answer cache')
