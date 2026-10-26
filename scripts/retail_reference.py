"""Scorer-only declared-policy references; never import into runtime arms.

Separate implementation is not independent expert business ground truth.
"""
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

CONTRACT = Path(__file__).resolve().parents[1] / 'research/retail-evaluation/evaluation-contract.json'
CONTRACT_SHA256 = '8b2c964ae312518cd75d6f56d761d23d35524a4814cabd712634789836ce49d6'

def _sign(value):
    if value is None or isinstance(value,bool):
        return None
    try:
        n=Decimal(str(value))
    except InvalidOperation:
        return None
    if not n.is_finite():
        return None
    return int(n.compare(Decimal(0)))

def reference_for(row_id, row, source_sha256):
    if not isinstance(row_id,str) or not row_id.strip():
        raise ValueError('Nonblank row ID required')
    if not isinstance(row,dict) or any(not isinstance(k,str) or not isinstance(v,(str,int,float,bool,type(None))) for k,v in row.items()):
        raise ValueError('Scalar source cells required')
    if not isinstance(source_sha256,str) or not re.fullmatch('[0-9a-f]{64}',source_sha256):
        raise ValueError('Source SHA256 required')
    raw=CONTRACT.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=CONTRACT_SHA256:
        raise ValueError('Reference contract changed; version and review required')
    version=json.loads(raw)['version']
    customer=row.get('CustomerID')
    present=customer is not None and bool(str(customer).strip())
    invoice=row.get('InvoiceNo')
    invoice_present=invoice is not None and bool(str(invoice).strip())
    quantity_sign=_sign(row.get('Quantity'))
    if not invoice_present or quantity_sign is None:
        qstatus,qcondition='unknown','invoice_missing_or_quantity_not_finite_decimal'
    else:
        is_cancel=str(invoice)[:1].casefold()=='c'
        expected_sign=-1 if is_cancel else 1
        qstatus='pass' if quantity_sign==expected_sign else 'violation'
        qcondition='cancel_requires_negative' if is_cancel else 'noncancel_requires_positive'
    price_sign=_sign(row.get('UnitPrice'))
    records=[
      ('customer_analysis','pass' if present else 'violation','customer_presence_only',['CustomerID']),
      ('quantity_sign',qstatus,qcondition,['InvoiceNo','Quantity']),
      ('nonnegative_price','unknown' if price_sign is None else ('violation' if price_sign==-1 else 'pass'),'finite_nonnegative_price',['UnitPrice']),
    ]
    return [{'row_id':row_id,'policy':policy,'status':status,'applied_condition':condition,'source_columns':columns,
             'policy_version':version,'policy_contract_sha256':CONTRACT_SHA256,'source_sha256':source_sha256,
             'reference_kind':'authored_policy_reference_not_business_truth'} for policy,status,condition,columns in records]
