import json,sys
from pathlib import Path
from projection import parse,compare

def run(sources,out):
 out=Path(out);out.mkdir(exist_ok=False,parents=True);results=[];parsed=[]
 for index,source in enumerate(sources):
  try:
   result=parse(source);parsed.append(result)
   (out/f'snapshot-{index}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
   results.append({'source':str(source),'status':'completed','sha256':result['sha256'],'nodes':len(result['nodes'])})
  except Exception as exc:results.append({'source':str(source),'status':'failed','error':type(exc).__name__+':'+str(exc)})
 (out/'outcomes.json').write_text(json.dumps(results,indent=2)+'\n')
 comparison=compare(*parsed) if len(parsed)==2 else {'status':'not_run','reason':'source_failure'}
 (out/'comparison.json').write_text(json.dumps(comparison,ensure_ascii=False,indent=2)+'\n')
 return results
if __name__=='__main__':run(sys.argv[1:3],sys.argv[3])
