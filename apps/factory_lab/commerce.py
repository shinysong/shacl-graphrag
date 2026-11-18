"""Keyless fictional shop administrator diagnostics. No mutation or LLM client."""
import argparse
import copy
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re
from rdflib import Graph, Namespace, RDF, Literal
from pyshacl import validate
from .explanation import canonical, owl_trace, term, SH

DEFAULT = Path(__file__).resolve().parents[2] / 'examples/commerce_lab/shop.json'
EX = Namespace('urn:commerce:')
# Strict import boundary: no arbitrary predicates, executable query or remote URL input.
SPECS = {
 'products': {'name':str,'category':str},
 'skus': {'product':str,'color':str,'size':str,'price':int,'warehouse':str,'available':(int,type(None)),'arrival':(str,type(None)),'arrival_confirmed':bool},
 'orders': {'status':str,'coupon':str,'shipping_policy':str,'requested_arrival':str},
 'items': {'order':str,'sku':str,'quantity':int},
 'coupons': {'minimum':int,'discount':int},
 'shipping_policies': {'minimum':int,'fee':int,'split_allowed':bool},
 'consents': {'order':str,'sku':str,'status':str},
 'approvals': {'order':str,'sku':str,'discount':int,'status':str},
 'cases': {'label':str,'question':str,'item':str,'replacement':str,'retain_discount':bool,'free_shipping':bool,'split':bool,'promise_arrival':bool},
}
REFERENCES={'skus':{'product':'products'},'orders':{'coupon':'coupons','shipping_policy':'shipping_policies'},'items':{'order':'orders','sku':'skus'},'consents':{'order':'orders','sku':'skus'},'approvals':{'order':'orders','sku':'skus'},'cases':{'item':'items','replacement':'skus'}}

def check_date(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):
        raise ValueError('Dates must use YYYY-MM-DD')
    date.fromisoformat(value)

def check_data(d):
    if not isinstance(d,dict) or set(d)!=set(SPECS)|{'schema_version','snapshot_id','as_of','currency'}:
        raise ValueError('Top-level fields must match the shop schema')
    if type(d['schema_version']) is not int or d['schema_version']!=1 or d['currency']!='KRW':
        raise ValueError('Only schema_version 1 and integer KRW are supported')
    if not isinstance(d['snapshot_id'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',d['snapshot_id']):raise ValueError('Invalid snapshot_id')
    check_date(d['as_of'])
    ids={}
    for table,spec in SPECS.items():
        rows=d[table]
        if not isinstance(rows,list) or len(rows)>200:raise ValueError(f'{table}: list of at most 200 records required')
        ids[table]=set()
        for row in rows:
            if not isinstance(row,dict) or set(row)!=set(spec)|{'id'}:raise ValueError(f'{table}: missing or unexpected fields')
            rid=row['id']
            if not isinstance(rid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',rid) or rid in ids[table]:raise ValueError(f'{table}: invalid/duplicate id')
            ids[table].add(rid)
            for key,kind in spec.items():
                allowed=kind if isinstance(kind,tuple) else (kind,)
                if type(row[key]) not in allowed:raise ValueError(f'{table}.{key}: invalid type')
                if isinstance(row[key],str) and len(row[key])>2000:raise ValueError('Text too long')
                if type(row[key]) is int and not 0<=row[key]<=1000000000:raise ValueError('Integer outside 0..1000000000')
            if table=='items' and row['quantity']==0:raise ValueError('Quantity must be positive')
            for key in ('arrival','requested_arrival'):
                if row.get(key) is not None:check_date(row[key])
            if table=='skus' and row['arrival_confirmed'] and row['arrival'] is None:raise ValueError('Confirmed arrival requires date')
            if table=='orders' and row['status'] not in ['unshipped','shipped']:raise ValueError('Unknown order status')
            if table in ('consents','approvals') and row['status'] not in ['approved','pending','rejected']:raise ValueError('Unknown approval status')
            if table=='products' and row['category'] not in ['RunningShoe','Socks']:raise ValueError('Unsupported category; update explicit adapter first')
    for table,refs in REFERENCES.items():
        for row in d[table]:
            for field,target in refs.items():
                if row[field] not in ids[target]:raise ValueError(f'{table}.{field}: dangling reference')
    for table in ('consents','approvals'):
        pairs=[(r['order'],r['sku']) for r in d[table]]
        if len(pairs)!=len(set(pairs)):raise ValueError(f'{table}: ambiguous duplicate order/sku records')
    if len({r['warehouse'] for r in d['skus']})>1:raise ValueError('Only one warehouse per input is supported')
    if any(c['discount']>c['minimum'] for c in d['coupons']):raise ValueError('Discount cannot exceed coupon minimum')
    if not d['cases']:raise ValueError('At least one authored case required')
    return d

def load(path=DEFAULT):
    path=Path(path)
    if path.stat().st_size>1000000:raise ValueError('Input exceeds 1 MB')
    raw=path.read_bytes();d=check_data(json.loads(raw))
    return d,sha256(raw).hexdigest()

def catalog(path=DEFAULT):
    d,h=load(path)
    return {'snapshot':d['snapshot_id'],'source_sha256':h,'cases':[{'id':c['id'],'label':c['label']} for c in d['cases']],
            'mode':'Authored administrator proposals; actual local queries/checks; no LLM or order mutation'}

def node(table,rid):return EX[f'{table}/{rid}']

def graph_data(d):
    g=Graph();g.bind('shop',EX)
    for table in SPECS:
        if table=='cases':continue # Authored questions/proposals are separate from source facts.
        for row in d[table]:
            n=node(table,row['id']);g.add((n,RDF.type,EX[table]))
            for key,value in row.items():
                if value is None:continue
                target=REFERENCES.get(table,{}).get(key)
                g.add((n,EX[key],node(target,value) if target else Literal(value)))
    return g

QUERY='''PREFIX shop: <urn:commerce:>
SELECT ?item ?sku ?quantity ?price WHERE {
 ?item shop:order ?order; shop:sku ?sku; shop:quantity ?quantity .
 ?sku shop:price ?price .
} ORDER BY ?item'''

RULES=[
 ('status','출고 전 주문만 변경할 수 있음','?v != "unshipped"'),
 ('same_product','같은 상품의 색상 옵션인지 확인','?v = false'),
 ('same_size','기존 사이즈 유지','?v = false'),
 ('stock_ok','기록된 가용 재고가 수량 이상인지 확인','?v = false'),
 ('consent','변경 옵션에 대한 고객 동의 필요','?v = false'),
 ('discount_ok','쿠폰 최소 금액 또는 해당 옵션의 예외 승인 필요','?v = false'),
 ('shipping_ok','무료배송 금액 조건 충족 필요','?v = false'),
 ('split_ok','부분 출고는 해당 정책이 허용해야 함','?v = false'),
 ('arrival_ok','도착 확약에는 요청일 이내 확정 근거 필요','?v = false'),
]
# Each derived value is a published calculation, not learned policy. Both comparators
# receive identical calculated features; the report does not prove RDF superiority.
def review(features, not_applicable=()):
    g=Graph();n=EX.Proposal;g.add((n,RDF.type,EX.ReviewPlan))
    for k,v in features.items():
        if v is not None:g.add((n,EX[k],Literal(v)))
    header='@prefix shop: <urn:commerce:> . @prefix sh: <http://www.w3.org/ns/shacl#> .\n'
    shapes=header+'\n'.join(f'''shop:Check_{key} a sh:NodeShape; sh:targetClass shop:ReviewPlan;
 sh:sparql [ sh:message "{key}"; sh:select """SELECT $this WHERE {{ $this <urn:commerce:{key}> ?v . FILTER({condition}) }}""" ] .''' for key,_,condition in RULES)
    conforms,rg,report=validate(g,shacl_graph=Graph().parse(data=shapes,format='turtle'),inference='none',advanced=True)
    results=[]
    for r in rg.subjects(RDF.type,SH.ValidationResult):
        results.append({'code':str(rg.value(r,SH.resultMessage)),'focus_node':term(rg.value(r,SH.focusNode)),
          'shape':term(rg.value(r,SH.sourceShape)),'property_path':term(rg.value(r,SH.resultPath)),'value':term(rg.value(r,SH.value))})
    python_flags=[k for k,_,_ in RULES if features[k] is not None and (features[k]!='unshipped' if k=='status' else features[k] is False)]
    results.sort(key=lambda r:r['code'])
    return {'conforms':bool(conforms),'results':results,'same_policy_python_flags':python_flags,
      'checks':[{'code':k,'label':label,'value':features[k],'status':'not_applicable' if k in not_applicable else 'unknown' if features[k] is None else 'violation' if k in [r['code'] for r in results] else 'pass'} for k,label,_ in RULES],
      'features':features,'data_turtle':g.serialize(format='turtle'),'shapes_turtle':shapes,'raw_report_turtle':rg.serialize(format='turtle'),
      'projection_notice':'Shared calculated features feed both Python and SHACL. This is a computed-feature diagnostic, not independent source-policy reasoning or RDF superiority.'}

def run_case(case_id,path=DEFAULT):
    d,source_hash=load(path)
    cases={c['id']:c for c in d['cases']}
    if case_id not in cases:raise ValueError('Unknown commerce case')
    plan=copy.deepcopy(cases[case_id]);lookup={t:{r['id']:r for r in d[t]} for t in SPECS}
    item=lookup['items'][plan['item']];order=lookup['orders'][item['order']]
    old=lookup['skus'][item['sku']];new=lookup['skus'][plan['replacement']]
    coupon=lookup['coupons'][order['coupon']];shipping=lookup['shipping_policies'][order['shipping_policy']]
    g=graph_data(d);rows=list(g.query(QUERY,initBindings={'order':node('orders',order['id'])}))
    before=sum(int(r.quantity)*int(r.price) for r in rows)
    subtotal=before-item['quantity']*old['price']+item['quantity']*new['price']
    consents=[r for r in d['consents'] if r['order']==order['id'] and r['sku']==new['id']]
    approvals=[r for r in d['approvals'] if r['order']==order['id'] and r['sku']==new['id']]
    approved=any(r['status']=='approved' and r['discount']==coupon['discount'] for r in approvals)
    eligible=subtotal>=coupon['minimum']
    discount=min(coupon['discount'],subtotal) if plan['retain_discount'] and (eligible or approved) else 0
    fee=0 if subtotal>=shipping['minimum'] else shipping['fee']
    arrival=None if new['arrival'] is None or not new['arrival_confirmed'] else new['arrival']<=order['requested_arrival']
    features={'status':order['status'],'same_product':old['product']==new['product'],'same_size':old['size']==new['size'],
      'stock_ok':None if new['available'] is None else new['available']>=item['quantity'],
      'consent':any(r['status']=='approved' for r in consents),
      'discount_ok':not plan['retain_discount'] or eligible or approved,
      'shipping_ok':not plan['free_shipping'] or subtotal>=shipping['minimum'],
      'split_ok':not plan['split'] or shipping['split_allowed'],
      'arrival_ok':(arrival is True) if plan['promise_arrival'] else None}
    report=review(features, () if plan['promise_arrival'] else ('arrival_ok',))
    unknown=[c['label'] for c in report['checks'] if c['status']=='unknown']
    if arrival is None:unknown.append('요청일 도착 여부: 확정 근거 부족')
    violations=[c for c in report['checks'] if c['status']=='violation']
    # Keep the whole query-scoped basket; other order items are not silently removed.
    facts={'order':order,'changed_item':item,'original_sku':old,'replacement_sku':new,
      'unchanged_items':[lookup['items'][str(r.item).rsplit('/',1)[-1]] for r in rows if r.item!=node('items',item['id'])],
      'coupon':coupon,'shipping_policy':shipping,'matching_consents':consents,'matching_approvals':approvals}
    selected_nodes={node('orders',order['id']),node('skus',old['id']),node('skus',new['id']),node('coupons',coupon['id']),node('shipping_policies',shipping['id'])}
    for r in rows:selected_nodes.update([r.item,r.sku])
    for table in ['consents','approvals']:
        selected_nodes.update(node(table,r['id']) for r in facts['matching_'+table])
    selected_nodes.update(node('products',lookup['skus'][str(n).rsplit('/',1)[-1]]['product']) for n in list(selected_nodes) if str(n).startswith(str(EX)+'skus/'))
    sub=Graph()
    for n in selected_nodes:
        for triple in g.triples((n,None,None)):sub.add(triple)
    nodes=[{'data':{'id':str(n),'label':str(n).rsplit('/',1)[-1],'kind':str(n).split('/')[-2].rsplit(':',1)[-1]}} for n in sorted(selected_nodes)]
    edges=[{'data':{'id':f'{s}|{p}|{o}','source':str(s),'target':str(o),'label':str(p).rsplit(':',1)[-1]}} for s,p,o in sub if o in selected_nodes]
    product=lookup['products'][new['product']]
    asserted=f'<{node("products",product["id"])}> a <urn:commerce:{product["category"]}> .'
    ontology='@prefix shop: <urn:commerce:> . @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> . shop:RunningShoe rdfs:subClassOf shop:Footwear . shop:Socks rdfs:subClassOf shop:Apparel .'
    owl=owl_trace(asserted,ontology)
    status='추가 확인 필요' if violations or unknown or arrival is False else '선언된 조건 충족 · 실행 승인 아님'
    def label(sku):
        # Display source labels literally inside inline Markdown, not as new markup.
        value=f"{lookup['products'][sku['product']]['name']} · {sku['color']} · {sku['size']}"
        return re.sub(r'([\\`*_{}\[\]()#+.!|>~-])', r'\\\1', value).replace('\n',' ')
    answer=f'## 관리자 처리안 검토\n\n**{status}**\n\n**{label(old)} → {label(new)}** 변경안을 검토했습니다. ({item["id"]}: {old["id"]} → {new["id"]}) 나머지 주문 항목은 유지합니다.\n\n'
    answer+=f'| 항목 | 원래 주문 | 변경안 |\n| --- | ---: | ---: |\n| 상품 합계 | {before:,}원 | {subtotal:,}원 |\n\n'
    answer+=f'- 변경안 정책상 적용 할인: **{discount:,}원**\n- 정책상 배송비: **{fee:,}원**\n- 산출 결제액: **{subtotal-discount+fee:,}원** (실제 청구·환불 아님)\n\n'
    answer+='### 필요한 확인과 다음 작업\n\n'
    answer+='\n'.join('- '+v['label'] for v in violations) if violations else '- 기록된 조건에서는 위반을 찾지 못했습니다.'
    answer+='\n'+ '\n'.join('- 미확인: '+u for u in unknown)
    if arrival is False:answer+='\n- 기록된 도착일은 고객 요청일 이후입니다. 일정 변경을 협의해야 합니다.'
    answer+='\n\n고객 동의·승인 기록과 최신 재고를 확인한 뒤 담당자가 결정해야 합니다. 저장된 도착일은 택배사의 실제 배송을 보장하지 않습니다.\n\n*이 문장은 로컬 계산 결과를 표시한 템플릿이며 LLM 답변이 아닙니다.*'
    return {'domain':'commerce','mode':'authored_admin_proposal_actual_local_engines','case_id':case_id,'question':plan['question'],'plan':plan,
      'source':{'snapshot':d['snapshot_id'],'as_of':d['as_of'],'source_sha256':source_hash,'currency':d['currency'],'absence_policy':'Consent/approval collections declared complete for this snapshot only; absent record is not real-world refusal.'},
      'facts':facts,'query':{'sparql':QUERY,'bindings':{'order':str(node('orders',order['id']))},'rows':[[str(v) for v in r] for r in rows]},
      'delivery_assessment':{'promised':plan['promise_arrival'],'confirmed_within_requested_date':arrival,'recorded_arrival':new['arrival'],'requested_arrival':order['requested_arrival']},
      'calculations':{'before_subtotal':before,'after_subtotal':subtotal,'discount':discount,'shipping_fee':fee,'total':subtotal-discount+fee,'policy':'Single seller, single currency, item prices before discount; shipping threshold uses pre-discount subtotal. Taxes/points/coupon expiry/stacking and refund settlement unsupported.'},
      'shacl':report,'owl':owl,'source_rdf':sub.serialize(format='turtle'),'graph':nodes+edges,'answer':answer,'unresolved':unknown,
      'limitations':['Authored scenarios, not natural errors or real commerce policy.','Template output, no LLM efficacy measurement.','Source absence is not retrieval omission: all selected order records queried from this declared complete snapshot.','No inventory reservation, order change, shipment, payment or customer message.','OWL classification does not establish coupon eligibility.','SHACL validates shared calculated features, not source truth.']}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('data',type=Path);p.add_argument('--case');p.add_argument('--output',type=Path);a=p.parse_args()
    try: result=run_case(a.case,a.data) if a.case else catalog(a.data)
    except (ValueError,TypeError,KeyError,OSError) as e:p.error(str(e))
    text=json.dumps(result,ensure_ascii=False,indent=2)
    if a.output:a.output.write_text(text+'\n')
    else:print(text)

if __name__=='__main__':main()
