"""Executable competing fixed queries; no new source facts or evaluator access."""
import json
from rdflib import Literal, XSD
from apps.factory_lab.graph import validate_args
from apps.factory_lab.rdf_graph import templates, decode
from experiments.factory_complexity.tools import RDFStudyTools

NEW_TOOLS = {'assigned_machines', 'current_qualification_records', 'expired_qualification_records'}


class CompetingTools:
    def __init__(self, backend):
        self.backend = backend
        self.views = backend.views

    def run(self, version, tool, args):
        if tool not in NEW_TOOLS:
            return self.backend.run(version, tool, args)
        if version != 'factory-v3':
            raise ValueError('Only current version is an entry point')
        assigned = tool == 'assigned_machines'
        alias = 'replacement_candidates' if assigned else 'qualification_records'
        validate_args(alias, args)
        data, digest = self.views.snapshot(version)
        value = next(iter(args.values()))
        if isinstance(self.backend, RDFStudyTools):
            query, roles, columns, limit = templates(version, alias, args)
            if assigned:
                old = '?order f:REQUIRES ?cap . ?machine f:CAPABLE_OF ?cap; f:id ?machine_id . ?cap f:id ?required_capability .'
                new = '?order f:ASSIGNED_TO ?machine . ?machine f:id ?machine_id . OPTIONAL { ?order f:REQUIRES ?cap . ?cap f:id ?required_capability }'
            else:
                old = 'OPTIONAL { ?machine f:HAS_QUALIFICATION ?qualification . ?qualification f:id ?qualification_id }'
                date = Literal(data['as_of'], datatype=XSD.date).n3()
                condition = f'?until < {date}' if tool.startswith('expired') else f'?start <= {date} && ?until >= {date}'
                new = '?machine f:HAS_QUALIFICATION ?qualification . ?qualification f:id ?qualification_id; f:valid_from ?start; f:valid_until ?until . FILTER('+condition+')'
            if query.count(old) != 1:
                raise ValueError('Template revision mismatch')
            query = query.replace(old, new)
            bindings = [{str(k): v for k, v in row.asdict().items()} for row in self.backend.dataset.query(query)]
            rows = decode(bindings, version, roles, columns)
        else:
            db = self.backend.db
            def node(ident):
                return json.loads(db.execute('SELECT props FROM nodes WHERE v=? AND id=?', (version, ident)).fetchone()[0])
            limit = 30
            if assigned:
                query = "SELECT e.b,c.b FROM edges e LEFT JOIN edges c ON c.v=e.v AND c.a=e.a AND c.r='REQUIRES' WHERE e.v=? AND e.a=? AND e.r='ASSIGNED_TO' ORDER BY e.b,c.b LIMIT 30"
                rows = [{'order':node(value), 'machine':node(m), 'required_capability':c} for m,c in db.execute(query,(version,value))]
            else:
                condition = "json_extract(n.props,'$.valid_until') < ?" if tool.startswith('expired') else "json_extract(n.props,'$.valid_from') <= ? AND json_extract(n.props,'$.valid_until') >= ?"
                query = "SELECT e.b FROM edges e JOIN nodes n ON n.v=e.v AND n.id=e.b WHERE e.v=? AND e.a=? AND e.r='HAS_QUALIFICATION' AND json_extract(n.props,'$.valid_from') IS NOT NULL AND json_extract(n.props,'$.valid_until') IS NOT NULL AND "+condition+" ORDER BY e.b LIMIT 30"
                dates = (data['as_of'],) if tool.startswith('expired') else (data['as_of'],data['as_of'])
                rows = [{'machine':node(value),'qualification':node(q)} for q, in db.execute(query,(version,value,*dates))]
        return {'tool':tool,'arguments':args,'snapshot':version,'source_sha256':digest,
            'as_of':data['as_of'],'rows':rows,'query':query,'backend':self.backend.name,
            'scope':'Selected-view fixed query. Date filtering only; not order eligibility, completeness or truth.',
            'limit_reached':len(rows)>=limit}
