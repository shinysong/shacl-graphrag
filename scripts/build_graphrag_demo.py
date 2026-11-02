"""Standalone HTML presentation of saved evidence; no model/retrieval execution."""
import base64,hashlib,html,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'research/graphrag-evidence-1'

def main():
    out=BASE/'demo-001';out.mkdir(exist_ok=False)
    paths=[BASE/'seminar-001/snapshot.json',BASE/'seminar-001/flow.svg',BASE/'seminar-copy.ko.md',ROOT/'docs/experiments/seminar/Pretendard-Regular.woff2',ROOT/'scripts/graphrag_demo.html',ROOT/'docs/experiments/seminar/OFL.txt']
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    snapshot=paths[0].read_text().replace('<','\\u003c')
    prose=paths[2].read_text().strip().split('\n## ')
    sections=''.join('<section class="explanation"><h3>'+html.escape(s.split('\n',1)[0].lstrip('# '))+'</h3><p>'+html.escape(s.split('\n',1)[1].strip())+'</p></section>' for s in prose)
    template=paths[4].read_text();text=template.replace('__FONT__',base64.b64encode(paths[3].read_bytes()).decode()).replace('__SNAPSHOT__',snapshot).replace('__FLOW__',paths[1].read_text()).replace('__EXPLANATION__',sections)
    (out/'index.html').write_text(text)
    (out/'flow.svg').write_bytes(paths[1].read_bytes())
    (out/'OFL.txt').write_bytes(paths[5].read_bytes())
    for p in paths:assert hashes[str(p.relative_to(ROOT))]==hashlib.sha256(p.read_bytes()).hexdigest()
    hashes['scripts/build_graphrag_demo.py']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (out/'manifest.json').write_text(json.dumps({'inputs':hashes,'html_sha256':hashlib.sha256((out/'index.html').read_bytes()).hexdigest(),'mode':'saved-result replay; no inference'},indent=2))
    print(out/'index.html')

if __name__=='__main__':main()
