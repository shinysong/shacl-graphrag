"""Catalog scaling: closed preparation, development-only offline checks, explicit scoring."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['prepare', 'offline', 'run', 'score'])
    parser.add_argument('--work')
    parser.add_argument('--split', choices=['development', 'evaluation'], default='evaluation')
    parser.add_argument('--results')
    parser.add_argument('--rubric')
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.command in ('prepare', 'run'):
        from experiments.query_contracts.scale_campaign import prepare, run
        if not args.work:
            parser.error('--work required')
        result = prepare(args.work, args.split) if args.command == 'prepare' else run(args.work)
    elif args.command == 'score':
        from experiments.query_contracts.scale_scoring import score
        if not all((args.results, args.rubric, args.output)):
            parser.error('--results --rubric --output required')
        result = score(json.loads(Path(args.results).read_text()), json.loads(Path(args.rubric).read_text()))
    else:
        from experiments.query_contracts.catalog_scale import packet, RecordTools, digest
        from experiments.query_contracts.scale_campaign import DATA, VIEWS, read
        from experiments.factory_complexity.tools import Views
        # No flag for evaluation: no retrieval inspection or tuning on reserved wording.
        requests = read(DATA / 'runtime/development.json')
        records = RecordTools(Views(VIEWS).snapshot('factory-v3')[0])
        rows = []
        query_checks = []
        original_checks = []
        try:
            from experiments.query_contracts.competing import CompetingTools
            from experiments.factory_complexity.tools import RDFStudyTools
            original = CompetingTools(RDFStudyTools(Views(VIEWS)))
            for contract in read(DATA / 'runtime/catalog-6.json'):
                argument, field = next(iter(contract['input'].items()))
                kind = field['semantic_type'][:-2]
                node = next(n for n in records.snapshot['nodes'] if n['kind'] == kind)
                out = original.run('factory-v3', contract['tool'], {argument: node['id']})
                original_checks.append({'tool': contract['tool'], 'rows': len(out['rows']),
                                        'result_sha256': digest(out)})
            for size in (6, 24, 72):
                contracts = read(DATA / 'runtime' / f'catalog-{size}.json')
                for request in requests:
                    for arm in ('full_catalog', 'retrieved'):
                        p = packet(request, contracts, arm)
                        rows.append({'size': size, 'arm': arm, 'request': request,
                                     'packet': p, 'input_bytes': p['input_bytes'],
                                     'model': 'offline_no_model', 'status': 'unattempted'})
            for contract in read(DATA / 'runtime/catalog-72.json'):
                if 'implementation' not in contract:
                    continue
                subject = contract['implementation']['subject']
                ident = next(k for k, v in records.entities.items() if v == subject)
                out = records.run(contract, {'literal': ident, 'kind': subject})
                query_checks.append({'tool': contract['tool'], 'rows': len(out['rows']),
                                     'scope': contract['implementation']['scope'],
                                     'result_sha256': digest(out)})
        finally:
            records.close()
        result = {'status': 'offline_only', 'slots': rows, 'query_checks': query_checks,
                  'original_query_checks': original_checks,
                  'model_calls': 0, 'tokens': None, 'actual_cost': None}
    if args.output:
        dest = Path(args.output)
        with dest.open('x') as stream:
            stream.write(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
        print(json.dumps({'output': str(dest), 'status': result.get('status')}))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
