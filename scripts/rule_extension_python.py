"""Independent new workflow composed beside the old PythonArm."""
from rule_extension_common import prepare, assemble


def evaluate(packet, policy):
    checks = prepare(packet, policy)
    failed, unknown = set(), set()
    for c in checks:
        v = c['values']
        if v is None:
            unknown.add(c['rule_id'])
            continue
        if c['kind'] == 'equal':
            ok = v[0] == v[1]
        elif c['kind'] == 'different':
            ok = v[0] != v[1]
        elif c['kind'] == 'interval':
            ok = v[0] <= v[1] < v[2]
        else:
            raise ValueError('unsupported predicate')
        if not ok:
            failed.add(c['rule_id'])
    return assemble(checks,failed,unknown)
