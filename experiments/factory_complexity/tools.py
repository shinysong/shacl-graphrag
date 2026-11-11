"""Read-only study adapters over hashed selected views, no evaluator imports."""
import copy
import hashlib
import json
import sqlite3
from pathlib import Path
from rdflib import Dataset, Literal, RDF, XSD
from apps.factory_lab.evidence import canonical
from apps.factory_lab.graph import TOOLS, NAMESPACE, RELATIONS, validate_args
from apps.factory_lab.rdf_graph import (VOCAB, FIELDS, KINDS, graph_uri, subject,
                                       templates, decode)

NOTICE = ('This is a synthetic read-only selected graph view. Source records may be omitted from this view; '
          'empty results do not establish source absence. Source hashes are provenance, not verdicts. '
          'Five tools query the current version. compare_impacted_orders queries previous/current selected views separately. '
          'The qualification reviewer checks retrieved replacement candidates only, not impact-list completeness or version changes. '
          'There is no schedule, load, delivery-date or renewal-document service. User reports are unverified. '
          'Never approve or perform physical allocation. Name specific human follow-up checks for unsupported questions.')
CATALOG = copy.deepcopy(TOOLS)+[{'type':'function','function':{
    'name':'compare_impacted_orders','description':'Read separately provenance-bound previous/current impact lists for a machine; not a complete change verdict.',
    'parameters':{'type':'object','properties':{'machine_id':{'type':'string'}},'required':['machine_id'],'additionalProperties':False}}}]


def sha(value):return hashlib.sha256(canonical(value).encode()).hexdigest()


def validate_view(data,version):
    if data.get('id')!=version or data.get('synthetic') is not True:raise ValueError('Invalid snapshot metadata')
    ids=[]
    for n in data['nodes']:
        if n.get('kind') not in KINDS or not n.get('id') or set(n)-set(FIELDS)-{'kind'}:raise ValueError('Invalid node')
        if any(not isinstance(v,str) for v in n.values()):raise ValueError('Non-string node value')
        ids.append(n['id'])
    if len(set(ids))!=len(ids):raise ValueError('Duplicate IDs')
    ids=set(ids)
    if len({tuple(e) for e in data['edges']})!=len(data['edges']):raise ValueError('Duplicate edges')
    for a,r,b in data['edges']:
        if a not in ids or b not in ids or r not in RELATIONS:raise ValueError('Invalid edge')


class Views:
    def __init__(self,directory):
        directory=Path(directory)
        self.manifest=json.loads((directory/'manifest.json').read_text())
        if set(self.manifest['versions'])!={'factory-v2','factory-v3'}:raise ValueError('Closed snapshot registry')
        self.data={}
        for version,meta in self.manifest['versions'].items():
            data=json.loads((directory/(version+'.json')).read_text());validate_view(data,version)
            if sha(data)!=meta['view_sha256']:raise ValueError('Selected-view hash mismatch')
            for field in ('source_sha256','view_sha256'):
                if len(meta[field])!=64 or any(c not in '0123456789abcdef' for c in meta[field]):raise ValueError('Invalid digest')
            self.data[version]=data
    def snapshot(self,version):
        if version not in self.data:raise ValueError('Unknown version')
        return copy.deepcopy(self.data[version]),self.manifest['versions'][version]['source_sha256']


class StudyTools:
    def __init__(self,views):self.views=views
    def run(self,version,tool,args):
        if version!='factory-v3':raise ValueError('Only current snapshot is a runtime entry point')
        if tool=='compare_impacted_orders':
            validate_args('impacted_orders',args)
            parts=[self._run(v,'impacted_orders',args) for v in ('factory-v2','factory-v3')]
            return {'tool':tool,'arguments':args,'snapshot':version,
                'source_sha256':parts[1]['source_sha256'],'as_of':parts[1]['as_of'],
                'rows':[{'version':p['snapshot'],'source_sha256':p['source_sha256'],
                    'scope':p['scope'],'rows':p['rows'],'limit_reached':p['limit_reached']} for p in parts],
                'scope':'Two selected-view listings; no claim of complete change detection.',
                'limit_reached':any(p['limit_reached'] for p in parts),'backend':self.name}
        return self._run(version,tool,args)
    def _run(self,version,tool,args):
        validate_args(tool,args)
        rows,query,limit=self.query(version,tool,args)
        d=self.views.data[version];meta=self.views.manifest['versions'][version]
        return {'tool':tool,'arguments':args,'snapshot':version,'source_sha256':meta['source_sha256'],
            'as_of':d['as_of'],'rows':rows,'query':query,'backend':self.name,
            'scope':'Selected view only; omissions possible; not source completeness.',
            'integrity':{'source_sha256':meta['source_sha256'],'view_sha256':meta['view_sha256']},
            'limit_reached':len(rows)>=limit}


class RDFStudyTools(StudyTools):
    name='study_rdflib'
    def __init__(self,views):
        super().__init__(views);self.dataset=Dataset()
        for version,data in views.data.items():
            g=self.dataset.graph(graph_uri(version))
            for n in data['nodes']:
                s=subject(version,n['id']);g.add((s,RDF.type,VOCAB[n['kind']]))
                for field in FIELDS:
                    if field in n:g.add((s,VOCAB[field],Literal(n[field],datatype=XSD.date if field.startswith('valid_') else None)))
            for a,r,b in data['edges']:g.add((subject(version,a),VOCAB[r],subject(version,b)))
    def query(self,version,tool,args):
        query,roles,columns,limit=templates(version,tool,args)
        bindings=[{str(k):v for k,v in row.asdict().items()} for row in self.dataset.query(query)]
        return decode(bindings,version,roles,columns),query,limit


class SQLStudyTools(StudyTools):
    name='study_sqlite'
    def __init__(self,views):
        super().__init__(views);self.db=sqlite3.connect(':memory:',check_same_thread=False)
        self.db.executescript('CREATE TABLE nodes(v TEXT,id TEXT,name TEXT,props TEXT,PRIMARY KEY(v,id)); CREATE TABLE edges(v TEXT,a TEXT,r TEXT,b TEXT,PRIMARY KEY(v,a,r,b)); CREATE INDEX reverse_edges ON edges(v,b,r,a);')
        for v,data in views.data.items():
            self.db.executemany('INSERT INTO nodes VALUES(?,?,?,?)',[(v,n['id'],n.get('name',''),canonical(dict(n,namespace=NAMESPACE,version=v,entity_id=n['id']))) for n in data['nodes']])
            self.db.executemany('INSERT INTO edges VALUES(?,?,?,?)',[(v,*e) for e in data['edges']])
        self.db.commit()
    def query(self,v,tool,args):
        value=next(iter(args.values()));limit=60 if tool=='inspect_entity' else 30
        node=lambda ident:json.loads(self.db.execute('SELECT props FROM nodes WHERE v=? AND id=?',(v,ident)).fetchone()[0]) if ident is not None else None
        if tool=='find_entities':
            q='SELECT props FROM nodes WHERE v=? AND (instr(lower(id),lower(?))>0 OR instr(lower(name),lower(?))>0) ORDER BY id LIMIT 30'
            rows=[{'entity':json.loads(r[0])} for r in self.db.execute(q,(v,value,value))]
        elif tool=='inspect_entity':
            q='SELECT r,a,CASE WHEN a=? THEN b ELSE a END AS neighbor FROM edges WHERE v=? AND (a=? OR b=?) ORDER BY r,neighbor LIMIT 60'
            exists=self.db.execute('SELECT id FROM nodes WHERE v=? AND id=?',(v,value)).fetchone()
            rows=[{'entity':node(value),'neighbor':node(b),'relation':r,'from_id':a} for r,a,b in self.db.execute(q,(value,v,value,value))] if exists else []
            if exists and not rows:rows=[{'entity':node(value),'neighbor':None,'relation':None,'from_id':None}]
        elif tool=='qualification_records':
            q="SELECT e.b FROM nodes n LEFT JOIN edges e ON e.v=n.v AND e.a=n.id AND e.r='HAS_QUALIFICATION' WHERE n.v=? AND n.id=? ORDER BY e.b LIMIT 30"
            rows=[{'machine':node(value),'qualification':node(b)} for b, in self.db.execute(q,(v,value))]
        elif tool=='impacted_orders':
            q="SELECT e.a,c.b FROM edges e LEFT JOIN edges c ON c.v=e.v AND c.a=e.a AND c.r='REQUIRES' WHERE e.v=? AND e.r='ASSIGNED_TO' AND e.b=? ORDER BY e.a,c.b LIMIT 30"
            rows=[{'order':node(o),'machine':node(value),'required_capability':c} for o,c in self.db.execute(q,(v,value))]
        else:
            q="SELECT m.a,c.b FROM edges c JOIN edges m ON m.v=c.v AND m.b=c.b AND m.r='CAPABLE_OF' WHERE c.v=? AND c.a=? AND c.r='REQUIRES' ORDER BY m.a,c.b LIMIT 30"
            rows=[{'order':node(value),'machine':node(m),'required_capability':c} for m,c in self.db.execute(q,(v,value))]
        return rows,q,limit
    def close(self):self.db.close()
