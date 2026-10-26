"""Posthoc annotation of saved disagreements; never execute or alter model artifacts."""
import hashlib
import json
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from scripts.retail_direct_pilot import write_new

ROOT = Path('_workspace/retail-llm-v1')
BASE = ROOT/'policy-specificity-v1'


def invoice_format(value):
    if value is None or isinstance(value, bool):
        return False
    text = str(value).strip()
    return (len(text) == 6 and text.isascii() and text.isdigit()) or (
        len(text) == 7 and text[0].lower() == 'c' and text[1:].isascii() and text[1:].isdigit())


def customer_format(value):
    # Saved selected cells are strings/null. Other types remain outside this annotation.
    if not isinstance(value, str):
        return None
    text = value.strip()
    return len(text) == 5 and text.isascii() and text.isdigit()


def fractional(value):
    try:
        number = Decimal(str(value))
        return number.is_finite() and number != number.to_integral_value()
    except (InvalidOperation, ValueError):
        return False


def main():
    saved = json.loads((BASE/'result.json').read_text())
    packets = json.loads((BASE/'packets.json').read_text())
    refs = {'random_development': json.loads((ROOT/'references.json').read_text()),
            'boundary_diagnostic': json.loads((ROOT/'boundary-v1/references.json').read_text())}
    origins = {c['row_id']:c['origin'] for c in json.loads((ROOT/'boundary-v1/cases.json').read_text())}
    annotations = []; counts = Counter(); all_flags = []
    for batch, packet in packets.items():
        rows = {r['row_id']:r['data'] for r in packet['rows']}
        pred = {(p['row_id'],p['policy']):p['status'] for p in saved['predictions']['underspecified'][batch]}
        for row_id, row in rows.items():
            all_flags.append({'row_id':row_id,'cohort':origins[row_id] if batch=='boundary_diagnostic' else batch,
                              'customer_matches_inspected_format':customer_format(row.get('CustomerID')),
                              'invoice_matches_inspected_format':invoice_format(row.get('InvoiceNo')),
                              'fractional_quantity':fractional(row.get('Quantity'))})
        for ref in refs[batch]:
            observed = pred[(ref['row_id'],ref['policy'])]
            if observed == ref['status']:
                continue
            row = rows[ref['row_id']]
            flags = []
            if ref['policy']=='customer_analysis' and customer_format(row.get('CustomerID')) is False:
                flags.append('customer_identifier_format_mismatch')
            if ref['policy']=='quantity_sign':
                if not invoice_format(row.get('InvoiceNo')):
                    flags.append('invoice_identifier_format_mismatch')
                if fractional(row.get('Quantity')):
                    flags.append('fractional_quantity_additional_gate')
            category = flags[0] if flags else 'unclassified_requires_inspection'
            counts[category] += 1
            annotations.append({'row_id':ref['row_id'],'cohort':origins[ref['row_id']] if batch=='boundary_diagnostic' else batch,
                                'policy':ref['policy'],'reference_status':ref['status'],'saved_status':observed,
                                'primary_category':category,'observed_flags':flags,
                                'evidence_cells':{k:row.get(k) for k in ('CustomerID','InvoiceNo','Quantity')},
                                'interpretation':'Posthoc co-occurrence with statically inspected code gates; no counterfactual replay or causal estimate'})
    assert len(annotations)==21 and sum(counts.values())==21
    paths=[BASE/'result.json',BASE/'packets.json',BASE/'calls/call-0000/output.ttl',
           ROOT/'references.json',ROOT/'boundary-v1/references.json',ROOT/'boundary-v1/cases.json',
           Path('_workspace/real-retail/metadata.json'),Path(__file__)]
    result={'scope':'Saved underspecified Python artifact; all38consumed rows annotated, no new trials',
            'categories':dict(counts),'disagreements':annotations,'row_format_flags':all_flags,
            'source_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
            'code_evidence':{'customer_id_is_valid':'Requires 5 ASCII digits after strip; lines44-57 in saved artifact',
                             'invoice_kind':'Requires 6 digits or C+6 digits after strip; lines59-67',
                             'quantity_gate':'Also requires integral decimal; lines88-89'},
            'limitations':['Format predicates describe this inspected artifact and literal metadata interpretation, not a full source-schema validator',
                           'SYN identifiers deliberately authored for prior sign/presence probes violate source-format descriptions',
                           'The same fractional probe also fails invoice format: isolated fractional-rule effect is unmeasured',
                           '21disagreements are repeated cells/rows, not21independent failures',
                           'No cases excluded, score recalculated, gold changed, artifact repaired or rerun',
                           'No natural prevalence, external business truth, causal information benefit or RDF advantage established']}
    write_new(Path('docs/experiments/records/20261020-retail-specificity-annotations.json'),result)
    print(json.dumps({'annotated_rows':len(all_flags),'disagreement_categories':dict(counts),'new_model_calls':0,'new_artifact_executions':0}))


if __name__=='__main__':
    main()
