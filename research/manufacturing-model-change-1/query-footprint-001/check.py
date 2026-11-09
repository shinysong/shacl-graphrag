from footprint import compare

def p(edges=(),types=()):return {'edges':set(edges),'types':set(types)}
def run(a,b,kind='model_object_members',target='A'):return compare(a,b,[{'kind':kind,'target':target}])['rows'][0]
r=run(p(types=[('old','A')]),p(types=[('old','A'),('new','A')]));assert r['changed'] and not r['flags']['previous_positive_paths_only'] and r['flags']['query_adjacency_buckets']
r=run(p(),p(types=[('new','A')]));assert r['old_values']==[] and r['flags']['query_adjacency_buckets']
r=run(p(types=[('old','B')]),p(edges=[('B','A')],types=[('old','B')]));assert r['flags']['query_adjacency_buckets'] and r['new_values']==['old']
r=run(p(types=[('old','A')]),p());assert r['flags']['previous_positive_paths_only'] and r['flags']['query_adjacency_buckets']
r=run(p(types=[('old','A')]),p(types=[('old','A'),('other','Z')]));assert not r['changed'] and not r['flags']['query_adjacency_buckets'] and r['flags']['whole_selected_graph']
r=run(p(edges=[('A','B')]),p(edges=[('A','B'),('B','C')]),'ancestors');assert r['flags']['query_adjacency_buckets'] and not r['flags']['previous_positive_paths_only']
print('six addition/empty/edge/deletion/unrelated/ancestor controls passed')
