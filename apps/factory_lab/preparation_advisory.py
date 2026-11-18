"""Bounded, inspectable commerce vocabulary suggestions; no model or truth claim.

Aliases are authored vocabulary. Context ranks candidate tables, not business
validity. Ties remain unresolved; values are shown for human review only.
"""
import re
import unicodedata
from . import preparation as p
from .commerce import REFERENCES
from .preparation_sources import relation_candidates

ALIASES = {
 'products.id':['product_id','상품번호'], 'products.name':['product_name','상품명'],
 'products.category':['분류','상품분류'],
 'skus.id':['sku_id','옵션번호'], 'skus.product':['product_id','상품번호'],
 'skus.color':['색상'], 'skus.size':['사이즈'], 'skus.price':['단가','unit_price'],
 'skus.warehouse':['창고'], 'skus.available':['가용재고','available_stock'],
 'skus.arrival':['도착예정일'], 'skus.arrival_confirmed':['도착확정'],
 'orders.id':['order_no','order_id','주문번호'], 'orders.status':['order_status','주문상태'],
 'orders.coupon':['coupon_id','쿠폰번호'], 'orders.shipping_policy':['배송정책'],
 'orders.requested_arrival':['요청도착일'],
 'items.id':['line_id','주문항목번호'], 'items.order':['order_no','order_id','주문번호'],
 'items.sku':['sku_id','옵션번호'], 'items.quantity':['qty','수량'],
 'coupons.id':['coupon_id','쿠폰번호'], 'coupons.minimum':['최소주문금액'],
 'coupons.discount':['할인금액'], 'shipping_policies.minimum':['무료배송기준금액'],
 'shipping_policies.fee':['배송비'], 'shipping_policies.split_allowed':['부분배송허용'],
 'consents.order':['order_no','주문번호'], 'consents.sku':['sku_id','옵션번호'],
 'consents.status':['동의상태'], 'approvals.order':['order_no','주문번호'],
 'approvals.sku':['sku_id','옵션번호'], 'approvals.status':['승인상태'],
 'approvals.discount':['승인할인금액'],
}

def normalized(value):
    # Deliberately not fuzzy/substring matching: refund_order_no != order_no.
    return re.sub(r'[\s_-]+','',unicodedata.normalize('NFKC',value).casefold())


def add_policy_comparisons(entries, sources):
    """Surface lexical differences, not a determination of policy conflict.

    Different scopes or dates can make both statements valid. Keep all counts
    and bounded source pointers; never choose the prevailing statement.
    """
    policies=[e for e in entries if e['kind']=='policy' and e['target']]
    hashes={s['name']:s['sha256'] for s in sources}
    fields=('basis','amount_expressions','effective_dates','exceptions')
    for entry in policies:
        hint=entry['extraction'];comparisons=[];count=0
        for other in policies:
            if other['id']==entry['id'] or other['target']!=entry['target']:continue
            differences=[f for f in fields if hint.get(f)!=other['extraction'].get(f)]
            if not differences:continue
            count+=1
            if len(comparisons)<8:
                source=other['source']
                comparisons.append({'entry_id':other['id'],'file':source['file'],
                    'paragraph':source['paragraph'],'line_start':source['line_start'],
                    'line_end':source['line_end'],'sha256':hashes[source['file']],
                    'different_fields':differences})
        if count:
            hint['related_policy_statements']=comparisons
            hint['related_policy_count']=count
            hint['questions'].append(f'같은 정책 후보의 다른 문단 {count}개와 금액·기준·시점·예외 표현이 다릅니다. 적용 대상이 다른지, 어떤 문서가 현재 유효한지 확인하세요. 표현 차이만으로 모순이라고 판단하지 않습니다.')

class AdvisoryGenerator(p.LocalGenerator):
    name='local-commerce-vocabulary-context-1'

    def suggest(self,sources):
        entries=super().suggest(sources)
        vocabulary={}
        for table,spec in self.specs.items():
            for field in ('id',*spec):
                target=f'{table}.{field}'
                for alias in [field,*ALIASES.get(target,[])]:
                    vocabulary.setdefault(normalized(alias),set()).add(target)
        refs={s['name']:s for s in sources}
        contexts={}
        for s in sources:
            if s['kind']!='table':continue
            scores={}
            for table in self.specs:
                matched={target for column in s['headers'] for target in vocabulary.get(normalized(column),set()) if target.startswith(table+'.')}
                scores[table]=len(matched)
            best=max(scores.values(),default=0)
            winners=[t for t,v in scores.items() if v==best and v>=2]
            contexts[s['name']]=(winners[0] if len(winners)==1 else None,scores)
        for e in entries:
            if e['kind']=='mapping':
                s=refs[e['source']['file']];column=e['source']['column']
                options=sorted(vocabulary.get(normalized(column),set()))
                context,scores=contexts[s['name']]
                narrowed=[v for v in options if context and v.startswith(context+'.')]
                # Retain the previous exact-schema proposal if it exists. New
                # suggestions require both unique table context and field match.
                if not e['target'] and len(narrowed)==1:e['target']=narrowed[0]
                e['extraction']={'method':self.name,'candidates':options,'table_candidate':context,
                    'table_scores':scores,'observed_values':[r[column] for r in s['rows'][:3]],
                    'questions':([f'{column}는 {e["target"]}을 뜻하나요? 원본 값과 업무 정의를 확인하세요.'] if e['target'] else
                                 [f'{column}는 어떤 업무 값인가요? 이름만으로 표준 필드를 정하지 못했습니다.'])}
                e['reason']='Authored alias vocabulary and co-occurring columns; human confirmation required'
            elif e['kind']=='policy':
                hint=e['extraction'];questions=[]
                if e['target'] in ('shipping','coupon') and hint['basis']=='unresolved':
                    questions.append('최소 금액은 할인 전 상품 합계인가요, 할인 후 결제 금액인가요?')
                if hint['exceptions']:questions.append('예외 대상과 우선 적용할 조건은 무엇인가요? 현재 고정 규칙이 이 예외를 처리할 수 있는지 확인하세요.')
                if not hint['effective_dates']:questions.append('이 정책은 언제부터 적용되나요? 자료 기준일에 유효한 정책인지 확인하세요.')
                if not e['target']:questions.append('이 문단은 참고 설명인가요, 적용할 정책인가요? 적용 대상과 규칙을 지정하세요.')
                hint['questions']=questions
        add_policy_comparisons(entries,sources)
        # Recompute bounded overlap proposals including reviewed-vocabulary ID
        # candidates. Overlap is still only a hypothesis, never an executed join.
        identifier_columns=set()
        for e in entries:
            if e['kind']=='mapping' and e['target']:
                table,field=e['target'].split('.')
                if field=='id' or field in REFERENCES.get(table,{}):
                    identifier_columns.add((e['source']['file'],e['source']['column']))
        entries=[e for e in entries if e['kind']!='relation']
        for index,candidate in enumerate(relation_candidates(sources,identifier_columns)):
            entries.append({'id':f'relation:{index}','kind':'relation','source':candidate['source'],
                            'target':candidate['target'],'reason':candidate['reason'],'overlap':candidate})
        return entries
