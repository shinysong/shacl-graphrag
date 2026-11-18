"""Source-bound human date roles, never automatic temporal interpretation."""
import re
from datetime import date

ROLES={'unresolved','start','end','context'}

def candidates(text):
    return [{'start':m.start(),'end':m.end(),'date':m.group(),'role':'unresolved'}
            for m in re.finditer(r'(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)',text)]

def validate(items, text=None):
    if not isinstance(items,list) or len(items)>256:raise ValueError('Invalid policy date roles')
    for item in items:
        if (not isinstance(item,dict) or set(item)!={'start','end','date','role'} or
            type(item['start']) is not int or type(item['end']) is not int or
            item['start']<0 or item['end']!=item['start']+10 or
            not isinstance(item['date'],str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',item['date']) or
            not isinstance(item['role'],str) or item['role'] not in ROLES):
            raise ValueError('Invalid policy date role')
    if text is not None and [{**v,'role':'unresolved'} for v in items]!=candidates(text):
        raise ValueError('Policy date roles must cover the exact source occurrences')

def require_applicable(items, as_of):
    starts=[];ends=[]
    for item in items:
        if item['role']=='unresolved':raise ValueError('Review each policy date as start, end, or context before approval')
        if item['role']=='context':continue
        value=date.fromisoformat(item['date']).isoformat()
        (starts if item['role']=='start' else ends).append(value)
    if len(starts)>1 or len(ends)>1:raise ValueError('Multiple applicability periods need a supported policy adapter')
    if starts and ends and starts[0]>ends[0]:raise ValueError('Policy start is after its end')
    if starts and as_of<starts[0]:raise ValueError('Policy starts after the snapshot date')
    if ends and as_of>ends[0]:raise ValueError('Policy expired before the snapshot date')
