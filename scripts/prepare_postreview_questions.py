"""Source-first development candidate inventory; no model calls or answer gold."""
import argparse,json,hashlib
from pathlib import Path
SOURCE=Path('research/refined-hybrid-1/neo4j-source-001/frozen/source-corpus-v1.json')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main(out,question_version=1):
    if question_version not in (1,2):raise ValueError('question version')
    out.mkdir(parents=True,exist_ok=False)
    corpus=json.loads(SOURCE.read_text());nodes={n['node_id']:n for n in corpus['nodes']};episodes=[];audit=[]
    if len(nodes)!=len(corpus['nodes']):raise ValueError('duplicate source nodes')
    for anchor in ['PP6:2','PP7:10']:
        node=nodes[anchor];src=node['source'];coupon=src['coupon'];row=src['excel_row']
        for family in ['recorded_position','defect_lookup','nominal_idc_lookup']:
            related=None
            if family=='recorded_position':
                question=f'제공된 자료에서 {coupon} 작업표 {row}행의 시작 위치 x_init 값과 단위를 출처와 함께 알려주세요.'
                if question_version==2:
                    question=f'제공된 자료에서 {coupon} 작업표 {row}행의 x_init [mm] 열에 기록된 시작 위치와 단위를 출처와 함께 알려주세요. x_init [# sample] 열의 표본 번호와 구분해주세요.'
                if 'x_init_mm' not in src['field_cells']:raise ValueError('no position field')
                source_ids=[anchor]; required_cells=[{'node_id':anchor,'cell':src['field_cells']['x_init_mm']}]
                implemented='atomic field agreement only; question-to-field mapping unverified'
            else:
                field='defect' if family=='defect_lookup' else 'welding_setting';related=src['dictionary_refs'][field];target=nodes[related]['source']
                if src['values'][field]!=target['code'] or src['sha256']!=target['sha256']:raise ValueError('reference/code or workbook mismatch')
                col='B' if family=='defect_lookup' else 'C';target_cell=col+str(target['excel_row'])
                cell=next(c for c in target['cells'] if c['cell']==target_cell)
                if cell['value'] is None or cell['formula'] is not None:raise ValueError('unsupported dictionary field')
                question=(f'제공된 자료에서 {coupon} 작업표 {row}행의 결함 코드가 같은 파일의 코드북에서 어떤 이름인지 두 출처를 연결해 설명해주세요.' if family=='defect_lookup' else f'제공된 자료에서 {coupon} 작업표 {row}행의 설정 번호를 같은 파일의 코드북에 연결해 명목 Idc 값과 단위를 알려주세요. 기록된 설정값과 실제 측정값을 구분해주세요.')
                source_ids=[anchor,related];required_cells=[{'node_id':anchor,'cell':src['field_cells'][field]},{'node_id':related,'cell':target_cell}];implemented='relational conclusion outside current atomic checker; requires separately declared lookup policy and review'
            for state in ['complete_selected','relevant_source_omitted']:
                selected=source_ids if state=='complete_selected' else ([anchor] if related else [])
                eid=f'{anchor.replace(":","-")}-{family}-{state}'
                episodes.append({'episode_id':eid,'question':question,'selected_evidence':[{'source_id':i,'source':nodes[i]['source']} for i in selected]})
                audit.append({'episode_id':eid,'family':family,'anchor':anchor,'control_state':state,'required_cells':required_cells,'source_bundle_contains_required_records':True,'selected_contains_required_records':all(i in selected for i in source_ids),'checker_readiness':implemented,'cohort_status':'consumed-source development candidate, not fresh heldout','question_provenance':'coordinator authored template from explicit source fields; no source truth guarantee'})
    (out/'candidate-runtime.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in episodes))
    (out/'offline-design-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
    manifest={'candidate_contexts':len(episodes),'base_questions':6,'anchors':2,'families':3,'evidence_states':2,'source':str(SOURCE),'source_sha256':sha(SOURCE),'script_sha256':sha(Path(__file__)),'source_attribution':corpus['source_attribution'],'paid_calls':0,'status':'unexecuted model candidates; not final experiment freeze','runtime_excludes':['control_state','required_cells','reference answers','offline checker_readiness'],'limitations':['source subset deliberately supplied rather than retrieval benchmark','current atomic checker does not verify relational conclusion','original corpus and anchors consumed development','no actual version/conflict policy present; do not invent one'],'hashes':{f.name:sha(f) for f in out.iterdir() if f.is_file()}}
    manifest['question_version']=question_version
    manifest['question_version_note']='v1 preserved; v2 explicitly selects millimetre header rather than sample-index header'
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:manifest[k] for k in ['candidate_contexts','base_questions','paid_calls','status']}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--question-version',type=int,choices=[1,2],default=1);a=p.parse_args();main(a.output,a.question_version)
