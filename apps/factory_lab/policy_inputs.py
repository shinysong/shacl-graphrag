"""Expose fixed-rule input provenance; no document interpretation or joins."""
from copy import deepcopy


def describe(draft, contracts):
    sources={s['name']:s for s in draft['sources']}
    result={}
    for target,contract in contracts.items():
        fields=[]
        for field in contract.get('fields',[]):
            matches=[e for e in draft['entries'] if e['kind']=='mapping' and e['target']==field and e['status']=='approved']
            item={'field':field,'state':'unreviewed' if not matches else 'ambiguous' if len(matches)>1 else 'available','records':[]}
            if len(matches)==1:
                entry=matches[0];ref=entry['source'];source=sources[ref['file']]
                item['source']={'file':source['name'],'sha256':source['sha256'],'column':ref['column']}
                item['mapping_entry_id']=entry['id']
                item['records']=[{'value':row[ref['column']],**deepcopy(location)} for row,location in zip(source['rows'],source['locations'])]
            fields.append(item)
        result[target]={'fields':fields,'notice':'Raw values from uniquely approved field mappings. Records are not joined across files. This display does not establish agreement with policy text; the fixed adapter determines calculations.'}
    return result
