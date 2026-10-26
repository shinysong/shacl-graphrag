"""Resident SQLite arm: native comparisons and recursive UNION, no Python UDF."""
import sqlite3
from pathlib import Path
from time import perf_counter_ns
from technology_selection_common import normalize, assemble, updated_packet, base
ROOT = Path(__file__).resolve().parents[1] / 'research/technology-selection'


class SQLiteArm:
    def __init__(self, packet):
        start = perf_counter_ns(); self.state = normalize(packet)
        self.normalization_ns = perf_counter_ns() - start
        start = perf_counter_ns()
        self.db = sqlite3.connect(':memory:')
        self.db.executescript('''CREATE TABLE checks(rule_id TEXT PRIMARY KEY,kind TEXT,a,b,c);
        CREATE TABLE edges(occurrence TEXT PRIMARY KEY,component_item TEXT,component_revision TEXT,parent_item TEXT,parent_revision TEXT);
        CREATE INDEX component_lookup ON edges(component_item,component_revision);''')
        self.receipt_sql = (ROOT / 'receipt-query-v1.sql').read_text()
        self.reach_sql = (ROOT / 'reach-query-v1.sql').read_text()
        self._load()
        self.setup_ns = perf_counter_ns() - start

    def _load(self):
        with self.db:
            self.db.execute('DELETE FROM checks'); self.db.execute('DELETE FROM edges')
            self.db.executemany('INSERT INTO checks VALUES(?,?,?,?,?)',
                [(c['rule_id'], c['kind'], *(c['values'] + [None] * (3-len(c['values']))))
                 for c in self.state['checks'] if c['values'] is not None])
            self.db.executemany('INSERT INTO edges VALUES(?,?,?,?,?)',
                [(occ, *node, *other) for node, edges in self.state['adjacency'].items() for occ, other in edges])

    def query(self):
        failed = {r[0] for r in self.db.execute(self.receipt_sql)}
        members = set(self.db.execute(self.reach_sql, self.state['target'] * 2))
        paths = base.shortest_paths(self.state['adjacency'], self.state['target'])
        return assemble(self.state, failed, members, paths)

    def update(self, command):
        start = perf_counter_ns(); p, changed = updated_packet(self.state, command)
        self.state = normalize(p); normalization_ns = perf_counter_ns()-start
        start = perf_counter_ns(); self._load()
        return dict(changed_occurrences=changed, normalization_ns=normalization_ns,
                    arm_apply_ns=perf_counter_ns()-start, invalidation='full common normalization; transactional table reload and index maintenance')

    def close(self):
        self.db.close()
