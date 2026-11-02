"""Build and execute a read-only seminar notebook from saved research artifacts."""
import hashlib,json,sys,tempfile
from pathlib import Path
import nbformat as nbf
from nbclient import NotebookClient
from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpecManager

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'research/graphrag-evidence-1'
OUT=BASE/'seminar-001'

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    OUT.mkdir(exist_ok=False)
    paths={'source':BASE/'source-corpus-v1.json','questions':BASE/'development-questions.json','D':BASE/'report-attachment-001/reports.jsonl'}
    for arm,directory in [('A','dense-retrieval-001'),('B','hybrid-retrieval-001')]:paths[arm]=BASE/directory/'retrieval.jsonl'
    for arm in ('C','E'):paths[arm]=BASE/'relation-retrieval-001'/f'{arm}.jsonl'
    for arm,directory in [('A','support-score-001'),('B','support-score-b-001'),('C','support-score-c-001'),('E','support-score-e-001')]:paths['score_'+arm]=BASE/directory/'scores.json'
    paths['copy']=BASE/'seminar-copy.ko.md'
    manifest={str(p.relative_to(ROOT)):digest(p) for p in paths.values()}
    source=json.loads(paths['source'].read_text());q=json.loads(paths['questions'].read_text())['questions']
    scores={a:json.loads(paths['score_'+a].read_text()) for a in 'ABCE'}
    records={a:{r['question_id']:r for r in map(json.loads,paths[a].read_text().splitlines())} for a in 'ABCED'}
    examples=['dev-006','dev-021','dev-017','dev-004']
    snapshot={'questions':q,'scores':scores,'source_attribution':source['source_attribution'],'source_inventory':source['inventory'],'examples':{i:{a:records[a][i] for a in 'ABCED'} for i in examples},'D_accounting':[{'question_id':i,**{k:r[k] for k in ['source_evidence_accounting_tokens','report_accounting_tokens','combined_accounting_tokens']}} for i,r in records['D'].items()],'D_summary':{'exact_C':sum(records['D'][i]['evidence']==records['C'][i] for i in records['C'])},'input_hashes':manifest}
    (OUT/'snapshot.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n')
    code=[]
    code.append('''# 저장된 결과를 읽고 파일 해시를 확인합니다. 모델은 호출하지 않습니다.
import json, hashlib
from pathlib import Path
snapshot_path = Path("snapshot.json")
assert hashlib.sha256(snapshot_path.read_bytes()).hexdigest() == SNAPSHOT_SHA
s = json.loads(snapshot_path.read_text())
print("질문 수:", len(s["questions"]))
print(json.dumps(s["source_attribution"], ensure_ascii=False, indent=2))''')
    code[0]='SNAPSHOT_SHA = '+repr(digest(OUT/'snapshot.json'))+'\n'+code[0]
    code.append('''# 질문과 실제로 선택된 노드의 원천 위치를 보여줍니다.
qid = "dev-006"
print(next(q["question"] for q in s["questions"] if q["question_id"] == qid))
for c in s["examples"][qid]["C"]["selected_chunks"]:
    if c["chunk_type"] == "node":
        node = json.loads(c["text"])
        print(json.dumps({k:node.get(k) for k in ["id","archive_path","sheet","excel_row","code","values","dictionary_refs","sha256"]}, ensure_ascii=False, indent=2))''')
    code.append('''# 비교 조건의 흐름을 로컬 SVG로 표시합니다.
from IPython.display import SVG, display
display(SVG(filename="flow.svg"))
print("C/E: 같은 근거·규칙, 다른 순회 구현 / D: C 근거 + 별도 보고서")''')
    code.append('''# 이미 저장된 사후 채점값을 비교합니다. 평가 정보를 검색에 전달하지 않습니다.
print("조건 | 근거 충족 / 원천 정보 있음 | 원천 부재 | 검색 실패")
for arm in "ABCE":
    summary = s["scores"][arm]["summary"]
    print(arm, summary["complete_support"], "/", summary["source_present"], summary["source_absent_separate"], summary["retrieval_state_counts"].get("retrieval_failure", 0))
assert [s["scores"][a]["summary"]["complete_support"] for a in "ABCE"] == [0,1,7,7]''')
    code.append('''# 같은 질문의 B와 C 선택 근거를 나란히 확인합니다.
for arm in "BCE":
    row = s["examples"]["dev-006"][arm]
    print(arm, row["status"], row["selected_chunk_ids"])
    score = next(r for r in s["scores"][arm]["results"] if r["question_id"] == "dev-006")
    print("필요 근거 충족:", score["complete_support"], "누락:", score.get("missing_node_sets"))
assert s["examples"]["dev-006"]["C"]["selected_chunks"] == s["examples"]["dev-006"]["E"]["selected_chunks"]''')
    code.append('''# 실패와 원천 부재를 다른 항목으로 확인합니다.
for qid in ["dev-017", "dev-004"]:
    row = s["examples"][qid]["C"]
    score = next(r for r in s["scores"]["C"]["results"] if r["question_id"] == qid)
    print(qid, "검색:", row["status"], row.get("error"))
    print("평가:", score["evidence_state"], "근거 충족:", score["complete_support"])
    if qid == "dev-017": print("후보 수:", len(row["candidate_chunk_ids"]))''')
    code.append('''# D는 C를 바꾸지 않으며 보고서 길이를 따로 기록합니다.
d = s["examples"]["dev-006"]["D"]
assert d["evidence"] == s["examples"]["dev-006"]["C"]
print(json.dumps(d["report"], ensure_ascii=False, indent=2))
print("C와 같은 근거:", s["D_summary"]["exact_C"])
print("합친 입력이 4096 E5 토큰 초과:", sum(r["combined_accounting_tokens"] > 4096 for r in s["D_accounting"]))
print("최대 합친 길이:", max(r["combined_accounting_tokens"] for r in s["D_accounting"]))
assert s["D_summary"]["exact_C"] == 24''')
    code.append('''# 입력 파일의 해시와 실행 범위를 출력합니다.
print(json.dumps(s["input_hashes"], indent=2))
print("노트북 실행: 저장된 결과 읽기·비교만 수행 / 검색·생성 모델 호출 없음")''')
    sections=paths['copy'].read_text().strip().split('\n## ')
    assert len(sections)==8
    cells=[]
    for i,(text,src) in enumerate(zip(sections,code)):
        cells.extend([nbf.v4.new_markdown_cell(text if i==0 else '## '+text),nbf.v4.new_code_cell(src)])
    svg='''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 940 260" role="img" aria-labelledby="title desc"><title id="title">저장된 근거의 처리 흐름</title><desc id="desc">같은 원천에서 A와 B 검색을 비교하고 B의 선택 근거를 C와 E로 확장합니다. D는 C 근거를 그대로 두고 보고서를 추가합니다.</desc><rect width="940" height="260" fill="white"/><g font-family="Pretendard, sans-serif" font-size="17" fill="#17232e" stroke="#596b7a" stroke-width="1.5"><rect x="15" y="90" width="140" height="60" rx="6" fill="#f5f7f9"/><rect x="205" y="30" width="170" height="60" rx="6" fill="#f5f7f9"/><rect x="205" y="160" width="170" height="60" rx="6" fill="#f5f7f9"/><rect x="430" y="120" width="200" height="60" rx="6" fill="#f5f7f9"/><rect x="430" y="190" width="200" height="55" rx="6" fill="#f5f7f9"/><rect x="700" y="120" width="220" height="60" rx="6" fill="#f5f7f9"/><path d="M155 110 L180 110 L180 60 L205 60 M155 130 L180 130 L180 190 L205 190 M375 190 L400 190 L400 150 L430 150 M400 190 L400 217 L430 217 M630 150 L700 150" fill="none"/><g stroke="none" text-anchor="middle"><text x="85" y="126">같은 원천 기록</text><text x="290" y="66">A 벡터 검색</text><text x="290" y="196">B 혼합 검색</text><text x="530" y="156">C 관계 확장</text><text x="530" y="223">E 같은 규칙의 SQL</text><text x="810" y="156">D C 근거 + 보고서</text></g></g></svg>'''
    (OUT/'flow.svg').write_text(svg)
    nb=nbf.v4.new_notebook(cells=cells,metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}})
    with tempfile.TemporaryDirectory() as tmp:
        kd=Path(tmp)/'kernels/python3';kd.mkdir(parents=True);(kd/'kernel.json').write_text(json.dumps({'argv':[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}'],'display_name':'Python 3','language':'python'}))
        manager=KernelManager(kernel_name='python3',kernel_spec_manager=KernelSpecManager(kernel_dirs=[str(kd.parent)]))
        try:NotebookClient(nb,km=manager,timeout=60,resources={'metadata':{'path':str(OUT)}}).execute()
        except Exception:
            nbf.write(nb,OUT/'walkthrough.failed.ipynb');raise
    nbf.validate(nb);nbf.write(nb,OUT/'walkthrough.ipynb')
    for path,h in manifest.items():assert digest(ROOT/path)==h
    receipt={'code_cells':8,'executed_code_cells':sum(c.cell_type=='code' and c.execution_count is not None for c in nb.cells),'errors':[o for c in nb.cells if c.cell_type=='code' for o in c.outputs if o.output_type=='error'],'input_hashes':manifest,'notebook_sha256':digest(OUT/'walkthrough.ipynb'),'snapshot_sha256':digest(OUT/'snapshot.json'),'builder_sha256':digest(__file__),'generation_executed':False}
    (OUT/'execution.json').write_text(json.dumps(receipt,indent=2));print(json.dumps({k:v for k,v in receipt.items() if k!='input_hashes'}))

if __name__=='__main__':main()
