"""Local Neo4j source graph adapter; parameterized queries, no answer references."""
import json
import re
import urllib.request
from scripts.graphrag_expand import _index, canonical


class Neo4jSource:
    def __init__(self, endpoint, namespace):
        if not re.fullmatch(r'http://127\.0\.0\.1:[0-9]{1,5}', endpoint):
            raise ValueError('explicit loopback HTTP endpoint required')
        if not 1 <= int(endpoint.rsplit(':', 1)[1]) <= 65535:
            raise ValueError('invalid port')
        if not re.fullmatch(r'[a-z0-9-]{1,80}', namespace):
            raise ValueError('invalid namespace')
        self.endpoint = endpoint + '/db/neo4j/tx/commit'
        self.namespace = namespace
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def query(self, statement, **params):
        payload = {'statements': [{'statement': statement,
            'parameters': {**params, 'run': self.namespace}, 'resultDataContents': ['row']}]}
        req = urllib.request.Request(self.endpoint, canonical(payload), {'Content-Type': 'application/json'})
        with self.opener.open(req, timeout=15) as response:
            body = json.load(response)
        if body.get('errors'):
            raise RuntimeError(json.dumps(body['errors']))
        result = body['results'][0]
        return [dict(zip(result['columns'], x['row'], strict=True)) for x in result['data']]

    def load(self, source):
        nodes, edges, _, node_chunks, edge_chunks = _index(source)
        if self.query('MATCH (n:Evidence {run:$run}) RETURN count(n) AS count')[0]['count']:
            raise ValueError('namespace already populated')
        self.query('UNWIND $rows AS row CREATE (n:Evidence {run:$run, id:row.id, chunk_id:row.chunk_id, payload:row.payload})',
            rows=[{'id':i,'chunk_id':node_chunks[i],'payload':canonical(n).decode()} for i,n in nodes.items()])
        self.query('UNWIND $rows AS row MATCH (s:Evidence {run:$run,id:row.subject}), (t:Evidence {run:$run,id:row.target}) CREATE (s)-[:SOURCE_REL {run:$run,id:row.id,chunk_id:row.chunk_id,payload:row.payload}]->(t)',
            rows=[{'id':i,'subject':e['subject'],'target':e['target'],'chunk_id':edge_chunks[i],'payload':canonical(e).decode()} for i,e in edges.items()])

    def outgoing(self, starts):
        if not isinstance(starts, list) or any(not isinstance(x,str) or not x for x in starts):
            raise ValueError('starts must be nonempty identifier strings')
        return self.query('MATCH (s:Evidence {run:$run})-[r:SOURCE_REL {run:$run}]->(t:Evidence {run:$run}) WHERE s.id IN $starts RETURN s.id AS subject,r.id AS edge_id,t.id AS target,r.chunk_id AS chunk_id,r.payload AS payload ORDER BY subject,edge_id', starts=sorted(set(starts)))

    def cleanup(self):
        self.query('MATCH (n:Evidence {run:$run}) DETACH DELETE n')
