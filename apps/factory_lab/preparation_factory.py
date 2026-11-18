"""CSV adapter for the existing synthetic factory selected-evidence diagnostic."""
import re
from types import SimpleNamespace
from .commerce import check_date

ADAPTER = 'factory-csv-1'
SPECS = {
    'machines': {'name':str,'status':str},
    'capabilities': {'name':str},
    'orders': {'name':str,'product':str},
    'qualifications': {'name':str,'product':str,'capability':str,'valid_from':str,'valid_until':str},
    'links': {'source':str,'relation':str,'target':str},
    'cases': {'label':str,'question':str,'order':str,'machine':str},
}
POLICIES = {
 'qualification': {'kind':'SHACL/selected-evidence','fields':['qualifications.product','qualifications.capability','qualifications.valid_from','qualifications.valid_until'],
                   'meaning':'Check retrieved qualification product, capability and inclusive validity dates against the selected order and snapshot date. Missing records are unknown, not approved.'},
 'availability': {'kind':'fixed-query/selected-evidence','fields':['machines.status','links.relation'],
                  'meaning':'Retrieve capability-linked replacement candidates and report recorded availability. This does not establish scheduling capacity or authorize physical allocation.'},
}
ONTOLOGY = ['CuttingCapability subClassOf ManufacturingCapability (CAP-CUT authored mapping only)']


def check(data):
    from .graph import RELATIONS
    kinds = {}
    expected = {'machines':'Machine','capabilities':'Capability','orders':'Order','qualifications':'Qualification'}
    check_date(data['as_of'])
    for table in SPECS:
        rows=data[table]
        if len(rows)>200: raise ValueError('Factory table exceeds 200 records')
        seen=set()
        for row in rows:
            if any(not isinstance(v,str) or len(v)>2000 for v in row.values()):
                raise ValueError('Factory fields must be bounded text')
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',row['id']) or row['id'] in seen:
                raise ValueError('Invalid or duplicate factory ID')
            seen.add(row['id'])
            if table in expected:
                if row['id'] in kinds: raise ValueError('Factory entity IDs must be globally unique')
                kinds[row['id']]=expected[table]
            if table=='machines' and row['status'] not in ('available','unavailable'):
                raise ValueError('Unsupported machine status')
            if table=='qualifications':
                check_date(row['valid_from']);check_date(row['valid_until'])
                if row['valid_from']>row['valid_until']: raise ValueError('Reversed qualification validity')
    signatures={'ASSIGNED_TO':('Order','Machine'),'REQUIRES':('Order','Capability'),
                'CAPABLE_OF':('Machine','Capability'),'HAS_QUALIFICATION':('Machine','Qualification')}
    edges=set()
    for row in data['links']:
        edge=(row['source'],row['relation'],row['target'])
        if edge in edges: raise ValueError('Duplicate factory relation')
        edges.add(edge)
        if row['relation'] not in RELATIONS or row['relation'] not in signatures:
            raise ValueError('Unsupported factory relation')
        if (kinds.get(row['source']),kinds.get(row['target']))!=signatures[row['relation']]:
            raise ValueError('Wrong or missing factory relation endpoints')
    for row in data['qualifications']:
        if kinds.get(row['capability'])!='Capability': raise ValueError('Qualification capability reference missing')
    if not data['cases']: raise ValueError('At least one authored factory case required')
    for row in data['cases']:
        if kinds.get(row['order'])!='Order' or kinds.get(row['machine'])!='Machine':
            raise ValueError('Case order/machine reference missing')
    return data


def execute(data,case_id):
    from experiments.factory_complexity.tools import RDFStudyTools, sha
    from experiments.query_contracts.competing import CompetingTools
    from .explanation import shacl_trace, owl_trace
    from .diagnostics import ASSERTED, ONTOLOGY as AXIOMS
    check(data)
    plan=next((r for r in data['cases'] if r['id']==case_id),None)
    if plan is None: raise ValueError('Unknown factory case')
    kinds={'machines':'Machine','capabilities':'Capability','orders':'Order','qualifications':'Qualification'}
    snapshot={'id':'factory-v3','as_of':data['as_of'],'synthetic':True,
              'source_scope':'User-reviewed preparation bundle; selected data only, completeness unverified',
              'nodes':[dict(row,kind=kind) for table,kind in kinds.items() for row in data[table]],
              'edges':[[r['source'],r['relation'],r['target']] for r in data['links']]}
    h=sha(snapshot)
    views=SimpleNamespace(data={'factory-v3':snapshot},manifest={'versions':{'factory-v3':{'source_sha256':h,'view_sha256':h}}})
    tools=CompetingTools(RDFStudyTools(views))
    candidates=tools.run('factory-v3','replacement_candidates',{'order_id':plan['order']})
    count=len(candidates['rows'])
    candidates['rows']=[r for r in candidates['rows'] if r['machine']['id']==plan['machine']]
    evidence=[candidates,tools.run('factory-v3','qualification_records',{'machine_id':plan['machine']})]
    report=shacl_trace(evidence)
    has_cut=any(r.get('required_capability')=='CAP-CUT' for r in candidates['rows'])
    return {'domain':'factory','case_id':case_id,'question':plan['question'],'plan':plan,
            'mode':'actual_local_fixed_queries_and_review_no_llm', 'evidence':evidence,'shacl':report,
            'owl':owl_trace(ASSERTED if has_cut else '',AXIOMS),
            'projection':{'rows_before':count,'rows_after':len(candidates['rows'])},
            'answer':f"제조 자료 검토: {plan['order']} / {plan['machine']}\n조회된 대체 후보 {len(candidates['rows'])}개를 검토했습니다. 상세 제약 결과와 미확인 사항을 아래 보고서에서 확인하세요.\n이 문장은 템플릿이며 LLM 답변이 아닙니다. 일정·납기·물리적 배치를 승인하지 않습니다.",
            'source_snapshot_id':data['snapshot_id'],
            'runtime_namespace':'factory-v3 is the existing query adapter namespace, not a historical snapshot identity'}
