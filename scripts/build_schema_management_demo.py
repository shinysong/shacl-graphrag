"""Render a standalone read-only replay from public archived study outputs."""
import json
from pathlib import Path


def build():
    base=Path('research/schema-management-1')
    def read(path):return json.loads((base/path).read_text())
    def optional(path):return read(path) if (base/path).exists() else None
    payload={'mapping':read('mapping-001/evaluation.json'),
             'questions':read('contracts-001/runtime-questions.json'),
             'references':read('contracts-001/evaluator-only-v2.json'),
             'raw':read('mapping-001/visible-responses.json'),
             'change':read('change-001/evaluation.json'),
             'semantics':optional('semantics-001/evaluation.json'),
             'semanticQuestions':read('semantics-001/questions.json'),
             'review':optional('review-001/evaluation.json'),
             'reports':optional('review-001/reports.json'),
             'cost':read('cost-snapshot.json'),'sources':read('source-001/manifest.json')}
    template=(base/'demo-template.html').read_text()
    assert template.count('__DATA__')==1
    encoded=json.dumps(payload,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    target=Path('docs/experiments/seminar/schema-management.html')
    target.write_text(template.replace('__DATA__',encoded))
    print(json.dumps({'target':str(target),'bytes':target.stat().st_size,
                      'mapping_rows':len(payload['mapping']['rows']), 'change_rows':len(payload['change']['rows']),
                      'semantics_rows':len(payload['semantics']['rows']) if payload['semantics'] else 0,
                      'review_rows':len(payload['review']['rows']) if payload['review'] else 0}))


if __name__=='__main__':build()
