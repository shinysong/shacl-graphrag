"""Read-only capability inventory; finding a command does not prove isolation."""
import json
import shutil
from pathlib import Path

OUT=Path('_workspace/retail-evaluation/readiness-v1.json')
def main():
    comparison=json.loads(Path('_workspace/retail-evaluation/row-compare-full-v1/summary.json').read_text())
    record={
      'command_paths':{name:shutil.which(name) for name in ('bwrap','nsjail','docker','podman','unshare','systemd-run')},
      'capability_verified':False,
      'inventory_limits':'PATH lookup only; no daemon access, containers, namespaces, installation, network or model calls; command availability is not isolation verification',
      'completed':['5000 consumed development rows / 15000 decisions per arm, authored Python vs row-graph SHACL','Saved raw trace illustrations','Independent declared-policy reference module on authored tests','Python/Turtle syntax-only intake and terminal intake failure scoring'],
      'observed_comparison':{'rows':comparison['rows'],'decisions_per_arm':comparison['decisions_per_arm'],'mismatch_count':len(comparison['mismatches']),'counts':comparison['counts']},
      'not_measured':['LLM direct decisions','LLM-generated ad hoc Python','LLM-generated reusable Python/SHACL','Human active time or accuracy','Maintenance effort and change-regression outcomes','Heldout610 cohort outcomes','External retailer business correctness'],
      'blocking_for_paid_launch':['Current heartbeat forbids paid calls; no revival of expired campaign','Model/settings and bounded paid scope not specified','Construction exposure and paired evaluation batches not frozen','Supported artifact grammar and concrete resource limits not frozen','Generated execution isolation not implemented or verified'],
      'next_decision':'Prioritize direct-LLM versus authored-code comparison when a new bounded paid scope is authorized; generated-code arms require additional execution isolation. Keep same shared metadata and distinguish raw-only LLM as separate condition.',
      'offline_next':'If installed isolation primitives exist, prepare a bounded local capability check for independent review, without installing software or launching new infrastructure. Otherwise consolidate results and stop recurring preparation rather than fabricate model progress.',
      'scope':'Readiness inventory, not a benchmark or execution authorization',
      'paid_calls':0}
    with OUT.open('x') as f:json.dump(record,f,indent=2)
    print(json.dumps(record))
if __name__=='__main__':main()
