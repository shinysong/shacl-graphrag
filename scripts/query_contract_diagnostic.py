"""Offline authored-plan integration diagnostic; not an LLM selector comparison."""
import argparse
import json
from pathlib import Path
from experiments.query_contracts.core import CatalogIndex, execute
from experiments.factory_complexity.tools import Views, RDFStudyTools, SQLStudyTools


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', required=True)
    parser.add_argument('--views', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists(): raise ValueError('Refuse to overwrite diagnostic')
    request = json.loads(Path(args.request).read_text())
    index = CatalogIndex()
    retrieval = {key: index.search(text) for key, text in request['obligations'].items()}
    views = Views(args.views); sql = SQLStudyTools(views)
    try:
        results = {'sqlite': execute(request, sql, max_calls=30),
                   'rdflib': execute(request, RDFStudyTools(views), max_calls=30)}
    finally: sql.close()
    record = {'scope': 'authored_plan_consumed_development_software_diagnostic',
        'selection': 'operator_authored; ranked shortlists NOT used to choose these steps',
        'retrieval': 'BM25 full metadata English words/Korean word+bigrams, not dense',
        'shortlists': retrieval, 'results': results,
        'equal_outputs': results['sqlite']['outputs'] == results['rdflib']['outputs'],
        'llm_calls': 0, 'answer_quality': 'unmeasured', 'selector_quality': 'unmeasured'}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')

if __name__ == '__main__': main()
