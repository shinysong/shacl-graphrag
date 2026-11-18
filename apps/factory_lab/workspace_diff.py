"""Compare saved review decisions without interpreting them as source truth."""
import json


def decision_changes(before, after):
    def indexed(draft):
        suggestions={e['id']:e for e in draft.get('saved_suggestions',[])}
        result={}
        for entry in draft['entries']:
            source=entry['source']
            identity=[entry['kind'],source['file'],source.get('column'),source.get('paragraph')]
            if entry['kind']=='relation':
                # Generated relation:N IDs can move when source order changes.
                # Match the original candidate endpoints, not its ordinal or
                # the mutable human-selected target.
                target=suggestions.get(entry['id'],entry)['target']
                identity.extend([target.get('file'),target.get('column')])
            key=json.dumps(identity,ensure_ascii=False)
            if key in result:raise ValueError('Ambiguous review identity in version comparison')
            result[key]=entry
        return result
    left,right=indexed(before),indexed(after)
    fields=('target','status','interpretation','note','temporal','agreement')
    changes=[]
    for key in sorted(left.keys()|right.keys()):
        old,new=left.get(key),right.get(key)
        changed=[f for f in fields if (old or {}).get(f)!=(new or {}).get(f)]
        if not changed and old is not None and new is not None:continue
        example=new or old
        changes.append({'kind':example['kind'],'source':example['source'],
            'change':'added' if old is None else 'removed' if new is None else 'updated',
            'changed_fields':changed,
            'before':{f:old.get(f) for f in fields} if old is not None else None,
            'after':{f:new.get(f) for f in fields} if new is not None else None,
            'before_entry_id':old['id'] if old else None,'after_entry_id':new['id'] if new else None})
    return changes
