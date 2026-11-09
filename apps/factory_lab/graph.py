"""Fixed, parameterized graph queries. Runtime exposes no arbitrary Cypher."""
import hashlib
import json
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'research/virtual-factory-llm-1'
NAMESPACE = 'virtual-factory-llm-1'
RELATIONS = {'ASSIGNED_TO', 'REQUIRES', 'CAPABLE_OF', 'HAS_QUALIFICATION'}

def snapshot(version):
    if version not in ('factory-v1', 'factory-v2'):
        raise ValueError('Unknown snapshot')
    raw = (DATA / (version + '.json')).read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()

class Graph:
    def __init__(self, url='http://127.0.0.1:7474'):
        if url != 'http://127.0.0.1:7474':
            raise ValueError('Only the owned loopback demo endpoint is allowed')
        self.url = url + '/db/neo4j/tx/commit'

    def query(self, cypher, params):
        with httpx.Client(timeout=15, trust_env=False) as client:
            r = client.post(self.url, json={'statements':[{'statement':cypher,'parameters':params}]})
        r.raise_for_status()
        obj = r.json()
        if obj.get('errors'):
            raise RuntimeError('Neo4j query rejected: ' + obj['errors'][0]['code'])
        result = obj['results'][0]
        return [dict(zip(result['columns'], d['row'])) for d in result['data']]

    def load(self, version):
        """Administrative idempotent import. Never delete or overwrite other versions."""
        d, sha = snapshot(version)
        params = {'ns':NAMESPACE,'v':version,'hash':sha}
        found = self.query('MATCH (s:FactorySnapshot {namespace:$ns, version:$v}) RETURN s.sha256 AS sha256', params)
        if found and any(x['sha256'] != sha for x in found):
            raise RuntimeError('Immutable snapshot hash conflict')
        # Namespace-qualified IDs avoid touching existing historical/user graphs.
        for n in d['nodes']:
            self.query('MERGE (n:FactoryDemo {namespace:$ns, version:$v, entity_id:$id}) SET n += $props',
                       params | {'id':n['id'],'props':n})
        for a, rel, b in d['edges']:
            if rel not in RELATIONS:
                raise ValueError('Unregistered relation')
            self.query('MATCH (a:FactoryDemo {namespace:$ns,version:$v,entity_id:$a}), '
                       '(b:FactoryDemo {namespace:$ns,version:$v,entity_id:$b}) '
                       f'MERGE (a)-[:{rel}]->(b)', params | {'a':a,'b':b})
        self.query('MERGE (s:FactorySnapshot {namespace:$ns,version:$v}) SET s.sha256=$hash', params)
        return {'version':version,'sha256':sha,'nodes':len(d['nodes']),'edges':len(d['edges'])}

    def run(self, version, tool, args):
        d, sha = snapshot(version)
        args = validate_args(tool,args)
        p = {'ns':NAMESPACE,'v':version} | args
        head = 'MATCH (n:FactoryDemo {namespace:$ns,version:$v}) '
        if tool == 'find_entities':
            q = head + 'WHERE toLower(n.entity_id) CONTAINS toLower($text) OR toLower(n.name) CONTAINS toLower($text) RETURN properties(n) AS entity ORDER BY n.entity_id LIMIT 30'
        elif tool == 'inspect_entity':
            q = head + 'WHERE n.entity_id=$entity_id OPTIONAL MATCH (n)-[r]-(m:FactoryDemo {namespace:$ns,version:$v}) RETURN properties(n) AS entity, type(r) AS relation, properties(m) AS neighbor, startNode(r).entity_id AS from_id ORDER BY relation, m.entity_id LIMIT 60'
        elif tool == 'impacted_orders':
            q = 'MATCH (o:FactoryDemo {namespace:$ns,version:$v})-[:ASSIGNED_TO]->(m:FactoryDemo {namespace:$ns,version:$v,entity_id:$machine_id}) OPTIONAL MATCH (o)-[:REQUIRES]->(c:FactoryDemo {namespace:$ns,version:$v}) RETURN properties(o) AS order, properties(m) AS machine, c.entity_id AS required_capability ORDER BY o.entity_id, c.entity_id LIMIT 30'
        elif tool == 'replacement_candidates':
            q = 'MATCH (o:FactoryDemo {namespace:$ns,version:$v,entity_id:$order_id})-[:REQUIRES]->(c:FactoryDemo {namespace:$ns,version:$v})<-[:CAPABLE_OF]-(m:FactoryDemo {namespace:$ns,version:$v}) RETURN properties(o) AS order, properties(m) AS machine, c.entity_id AS required_capability ORDER BY m.entity_id, c.entity_id LIMIT 30'
        elif tool == 'qualification_records':
            q = 'MATCH (m:FactoryDemo {namespace:$ns,version:$v,entity_id:$machine_id}) OPTIONAL MATCH (m)-[:HAS_QUALIFICATION]->(r:FactoryDemo {namespace:$ns,version:$v}) RETURN properties(m) AS machine, properties(r) AS qualification ORDER BY r.entity_id LIMIT 30'
        else:
            raise ValueError('Unknown tool')
        # Provenance binds actual DB content to the file used to import it.
        stored = self.query('MATCH (s:FactorySnapshot {namespace:$ns,version:$v}) RETURN s.sha256 AS sha256',p)
        if len(stored) != 1 or stored[0]['sha256'] != sha:
            raise RuntimeError('Snapshot not loaded or hash differs')
        rows = self.query(q,p)
        return {'tool':tool,'arguments':args,'snapshot':version,'source_sha256':sha,'as_of':d['as_of'],
                'query':q,'rows':rows,'scope':'selected query result in authored snapshot; not completeness proof',
                'limit_reached':len(rows) >= (60 if tool=='inspect_entity' else 30)}

ARGS = {'find_entities':'text','inspect_entity':'entity_id','impacted_orders':'machine_id',
        'replacement_candidates':'order_id','qualification_records':'machine_id'}

def validate_args(tool,args):
    if tool not in ARGS or not isinstance(args,dict) or set(args)!={ARGS[tool]}:
        raise ValueError('Invalid tool arguments')
    value = args[ARGS[tool]]
    if not isinstance(value,str) or not 1 <= len(value) <= 100:
        raise ValueError('Tool argument must be a nonempty bounded string')
    return args

DESCRIPTIONS = {
 'find_entities':'Find entity IDs by literal ID/name substring. Empty search not allowed.',
 'inspect_entity':'Read an entity and its adjacent graph relations, including direction.',
 'impacted_orders':'Find orders assigned to this machine and their required capabilities.',
 'replacement_candidates':'Find machines linked to capabilities required by this order. These are only capability candidates, not approved alternatives. Fetch qualification records separately.',
 'qualification_records':'Retrieve available qualification records for a machine. Absence in results is not proof of real-world absence.'}
TOOLS = [{'type':'function','function':{'name':name,'description':DESCRIPTIONS[name],
          'parameters':{'type':'object','properties':{arg:{'type':'string'}},'required':[arg],'additionalProperties':False}}}
         for name,arg in ARGS.items()]
