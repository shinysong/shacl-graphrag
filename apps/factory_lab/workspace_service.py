"""Persistent single-user workflow API; no paid calls or business mutations."""
from . import preparation as p
from .preparation_service import PreparationService
from .workspace_store import WorkspaceStore
from .preparation_sources import inspect_sources
from .preparation_advisory import AdvisoryGenerator
from . import workspace_lookup, policy_dates, policy_inputs, policy_agreement
from .workspace_diff import decision_changes
from .workspace_references import column_references
from .preparation_model import ModelProposalGenerator
from . import workspace_policy, workspace_question, workspace_documents, workspace_relations, workspace_readiness


class OperationCancelled(RuntimeError):
    pass


class WorkspaceService:
    def __init__(self, path, proposal_gateway=None, question_gateway=None, local_reasoner=None,
                 database_registry=None, source_documents=None):
        self.store = WorkspaceStore(path)
        self.proposal_gateway=proposal_gateway
        self.question_gateway=question_gateway
        self.local_reasoner=local_reasoner
        self.source_documents=source_documents
        from .workspace_database_adapter import DatabaseWorkspaceAdapter
        self.database_adapter=(DatabaseWorkspaceAdapter(database_registry)
                               if database_registry is not None else None)

    def _database(self):
        if self.database_adapter is None:
            raise ValueError('Registered database adapter is not configured')
        return self.database_adapter

    def _restore(self, draft):
        if isinstance(draft,dict) and draft.get('adapter')=='registered-database-1':
            return self._database().restore(draft)
        return p.restore_draft(draft)

    def _database_view(self, row):
        from .workspace_reasoning import capability
        draft=self._database().restore(row['draft'])
        catalog=self._database().row_catalog(draft)
        unsupported='Unsupported for database source-row workspaces'
        from .workspace_database_example import describe
        from .workspace_extension_summary import latest
        from .workspace_proposal_language import latest as localized
        return {**row,'draft':draft,'database_capabilities':draft['capabilities'],
                'latest_extension':latest(self.store,row['id'],row['revision']),
                'proposal_korean':localized(self.store,row),
                'proposal_translation_enabled':self.proposal_gateway is not None,
                'database_example':describe(self._database().registry,draft),
                'local_reasoning':capability(self.local_reasoner),
                'task_readiness':{'capabilities':{'source_rows':len(catalog),
                    'source_document':0,'relation_rows':0,'stock_check':0},
                    'replacement':None,'notice':unsupported},
                'policy_inputs':{},'contracts':{},'cases':[],
                'readiness':{'ready':False,'reason':unsupported},
                'review_buffer':self.store.review_buffer(row['id']),
                'column_references':{},'policy_agreements':{},'policy_groups':{},
                'policy_date_candidates':{},
                'model_questions':{'enabled':self.question_gateway is not None,
                    'model':self.question_gateway.config.get('model') if self.question_gateway else None,
                    'route':'database-question-1',
                    'reason':None if self.question_gateway else 'Question model is not enabled on this server'},
                'model_proposals':{'enabled':False,'model':None,'reason':unsupported},
                'source_documents_enabled':self.source_documents is not None,
                'relation_catalog':[],'document_catalog':[],'lookup_catalog':[],
                'row_lookup_catalog':catalog,'mapping_targets':['source_only'],
                'versions':self.store.revisions(row['id']),**self.store.operation_page(row['id'])}

    def _database_action(self, action, body, row):
        """Separate generic source reuse from fixed-domain policy execution."""
        adapter=self._database()
        key,revision=row['id'],row['revision']
        if action=='lookup':
            operation,created=self.store.begin(key,revision,body['request_key'],
                'source_lookup',{'selection':body['selection']})
            if created:
                try:
                    result=workspace_lookup.execute(row['draft'],body['selection'],database_adapter=adapter)
                    result['workspace']={'id':key,'revision':revision,'draft_digest':row['digest']}
                    self.store.finish(operation['id'],'completed',result=result)
                except (ValueError,KeyError,TypeError) as exc:
                    self.store.finish(operation['id'],'failed',error=str(exc)[:1000])
                except Exception:
                    self.store.finish(operation['id'],'failed',error='Local database execution failed; inspect before retry')
                    raise
            return {'operation':self.store.operation(key,operation['id']),'reused':not created}
        draft=adapter.restore(row['draft'])
        if action=='export':
            return {'format':'workspace-draft-1','workspace_id':key,'revision':revision,
                    'draft':draft,'digest':row['digest'],
                    'review_resolved':all(e['status'] in ('approved','excluded') for e in draft['entries'])}
        if action=='change':
            decisions=body['decisions']
            fields={'entry_id','status','target','note','interpretation'}
            if (not isinstance(decisions,list) or not 1<=len(decisions)<=p.MAX_ENTRIES or
                    any(not isinstance(d,dict) or set(d)!=fields or not isinstance(d['entry_id'],str)
                        for d in decisions) or len({d['entry_id'] for d in decisions})!=len(decisions)):
                raise ValueError('Provide distinct bounded database review decisions')
            for decision in decisions:
                draft=adapter.change(draft,**decision)
            self.store.save(key,draft,revision)
            return self.view(key)
        if action=='save_review_buffer':
            content=body['content']
            if (not isinstance(content,dict) or set(content)-{'comparisons'}!={'entries','policies'}
                    or content['policies']!=[] or content.get('comparisons',[])!=[]):
                raise ValueError('Database review buffers support field decisions only')
            entries=content['entries']
            fields={'entry_id','status','target','note','interpretation'}
            known={e['id'] for e in draft['entries']}
            if (not isinstance(entries,list) or len(entries)>len(known) or
                    any(not isinstance(e,dict) or set(e)!=fields or not isinstance(e['entry_id'],str)
                        or e['entry_id'] not in known for e in entries) or
                    len({e['entry_id'] for e in entries})!=len(entries)):
                raise ValueError('Invalid database review buffer')
            for entry in entries:
                # Buffers may be incomplete; they cannot authorize a lookup.
                if (entry['status'] not in ('pending','approved','excluded','insufficient') or
                        entry['target']!='source_only' or any(not isinstance(entry[k],str) or len(entry[k])>4000
                            for k in ('note','interpretation'))):
                    raise ValueError('Invalid database review buffer decision')
            return self.store.save_review_buffer(key,revision,body['generation'],content)
        raise ValueError('Unsupported database workspace action; only field review and exact source-row reuse are enabled')

    def view(self, key, revision=None):
        from .workspace_reasoning import capability
        row = self.store.get(key,revision)
        if row['draft'].get('adapter')=='registered-database-1':
            return self._database_view(row)
        specs,contracts=p.adapter_config(row['draft']['adapter'])
        try:
            workspace_policy.require_ready(row['draft'])
            data=p.materialize(row['draft'])
            readiness={'ready':True,'reason':None}
            cases=[{k:case[k] for k in ('id','label','question') if k in case} for case in data['cases']]
        except ValueError as exc:
            readiness={'ready':False,'reason':str(exc)[:1000]}
            cases=[]
        return {**row,'local_reasoning':capability(self.local_reasoner),'task_readiness':workspace_readiness.describe(row['draft']),'policy_inputs':policy_inputs.describe(row['draft'],contracts),'contracts':contracts,'readiness':readiness,'cases':cases,
                'review_buffer':self.store.review_buffer(key),
                'column_references':column_references(row['draft']),
                'policy_agreements':{e['id']:policy_agreement.status(row['draft'],e['id']) for e in row['draft']['entries'] if e['kind']=='policy' and e['target'] in contracts},
                'policy_groups':workspace_policy.groups(row['draft']),
                'policy_date_candidates':{e['id']:policy_dates.candidates(e['source']['text']) for e in row['draft']['entries'] if e['kind']=='policy'},
                'model_questions':{'enabled':self.question_gateway is not None,
                    'model':self.question_gateway.config['model'] if self.question_gateway else None},
                'model_proposals':{'enabled':self.proposal_gateway is not None,
                    'model':self.proposal_gateway.config['model'] if self.proposal_gateway else None},
                'relation_catalog':workspace_relations.catalog(row['draft']),
                'document_catalog':workspace_documents.catalog(row['draft']),
                'lookup_catalog':workspace_lookup.catalog(row['draft']),
                'row_lookup_catalog':workspace_lookup.row_catalog(row['draft']),
                'mapping_targets':[f'{table}.{field}' for table,spec in specs.items() for field in ('id',*spec)],
                'versions':self.store.revisions(key),**self.store.operation_page(key)}

    def handle(self, body):
        schemas = {
            'list':{'archived'}, 'create':{'title','files','metadata','domain'},
            'create_database':{'title','source_id','metadata','domain'},
            'database_sources':set(),
            'example_database':set(),
            'example':{'domain'}, 'get':{'id','revision'},
            'cancel':{'id','request_key'},
            'progress':{'id','request_key'}, 'operation':{'id','operation_id'}, 'history':{'id','before'},
            'import':{'title','bundle'},
            'local_reasoning':{'id','revision','request_key','asserted_base64','profile'},
            'extension_import':{'id','revision','request_key','raw_base64'},
            'extension_review_batch':{'id','revision','request_key','operation_id','decisions'},
            'extension_review':{'id','revision','request_key','operation_id','candidate_id','entry_id',
                                'target','interpretation','note','manual_binding'},
            'save_review_buffer':{'id','revision','generation','content'},
            'add_relation':{'id','revision','source','target','reason'},
            'change':{'id','revision','decisions'}, 'refresh':{'id','revision','files'},
            'archive':{'id','archived'}, 'export':{'id','revision'},
            'execute':{'id','revision','request_key','case_id'},
            'propose':{'id','revision','request_key','proposal'},
            'lookup':{'id','revision','request_key','selection'},
            'suggest':{'id','revision','request_key'},
            'ask':{'id','revision','request_key','question'},
            'withdraw_pending':{'id','revision','request_key','kind','request'},
            'adopt_suggestions':{'id','revision','operation_id'},
            'resolve_policy':{'id','revision','target','selected_id','rationale'},
            'compare_policy':{'id','revision','entry_id','binding','decision','basis','rationale'},
            'diff':{'id','before','after'},
        }
        from .workspace_document_service import ACTIONS as DOCUMENT_ACTIONS
        from .workspace_query_service import ACTIONS as QUERY_ACTIONS
        from .workspace_query_reasoning_service import ACTIONS as REASONING_ACTIONS
        from .workspace_question_scope import ACTIONS as SCOPE_ACTIONS
        from .workspace_database_shapes_service import ACTIONS as SHAPES_ACTIONS
        schemas.update(DOCUMENT_ACTIONS)
        schemas.update(QUERY_ACTIONS)
        schemas.update(REASONING_ACTIONS)
        schemas.update(SCOPE_ACTIONS)
        schemas.update(SHAPES_ACTIONS)
        from .workspace_proposal_language import ACTION as LOCALIZE, FIELDS as LOCALIZE_FIELDS
        schemas[LOCALIZE]=LOCALIZE_FIELDS
        action = body.get('action')
        # Older clients retain the recorded metadata; newer clients can provide
        # an explicit complete snapshot description with the same source files.
        if action=='refresh' and 'metadata' in body:
            schemas['refresh']=schemas['refresh']|{'metadata'}
        if not isinstance(action,str) or action not in schemas or set(body)!=schemas[action]|{'action'}:
            raise ValueError('Unknown workspace action or fields')
        if action=='example_database':
            from .workspace_database_example import create
            draft=create(self._database())
            row=self.store.create('쇼핑몰 SQLite 연결 예시',draft)
            return self.view(row['id'])
        if action=='database_sources':
            return self.database_adapter.sources() if self.database_adapter else {
                'enabled':False,'sources':[],'truncated':False}
        if action=='list':
            if type(body['archived']) is not bool: raise ValueError('Archive filter must be boolean')
            return {'workspaces':self.store.list(body['archived'])}
        if action=='import':
            bundle=body['bundle']
            if not isinstance(bundle,dict) or set(bundle)!={'format','workspace_id','revision','draft','digest','review_resolved'} or bundle['format']!='workspace-draft-1':
                raise ValueError('Invalid working draft export')
            if p.digest(bundle['draft'])!=bundle['digest']:
                raise ValueError('Working draft digest mismatch')
            draft=self._restore(bundle['draft'])
            # Imported identity never overwrites a current workspace or copies
            # execution outcomes. Approval is replayed, not authenticated.
            row=self.store.create(body['title'],draft)
            return self.view(row['id'])
        if action=='create_database':
            draft=self._database().create(body['source_id'],body['metadata'],domain=body['domain'])
            row=self.store.create(body['title'],draft)
            return self.view(row['id'])
        if action in ('example','create'):
            if body['domain'] not in ('commerce','factory'):raise ValueError('Unknown domain')
            adapter=body['domain']+'-csv-1'
            if action=='example':
                draft=PreparationService().handle({'action':'example','adapter':adapter})['draft']
                if body['domain']=='commerce':
                    draft=p.create([{'name':s['name'],'content':s['content']} for s in draft['sources']],
                                   draft['metadata'],generator=AdvisoryGenerator())
                title='쇼핑몰 운영 자료' if body['domain']=='commerce' else '제조 자료'
            else:
                draft=p.create(body['files'],body['metadata'],adapter=adapter,
                               generator=AdvisoryGenerator() if body['domain']=='commerce' else None)
                title=body['title']
            row=self.store.create(title,draft)
            return self.view(row['id'])
        key=body['id']
        if not isinstance(key,str):raise ValueError('Invalid workspace ID')
        if action=='cancel':return self.store.request_cancel(key,body['request_key'])
        if action=='progress':return self.store.progress(key,body['request_key'])
        if action=='history':return self.store.operation_page(key,body['before'])
        if action=='operation':
            if not isinstance(body['operation_id'],str):raise ValueError('Invalid operation ID')
            return self.store.operation(key,body['operation_id'])
        if action=='get':
            version=body['revision']
            if version is not None and (type(version) is not int or version<1):raise ValueError('Invalid revision')
            return self.view(key,version)
        if action=='archive':
            if type(body['archived']) is not bool:raise ValueError('Archive state must be boolean')
            self.store.archive(key,body['archived'])
            return self.view(key)
        if action=='diff':
            if any(type(body[k]) is not int or body[k]<1 for k in ('before','after')):raise ValueError('Invalid revision')
            before=self.store.get(key,body['before'])['draft'];after=self.store.get(key,body['after'])['draft']
            left={s['name']:s['sha256'] for s in before['sources']};right={s['name']:s['sha256'] for s in after['sources']}
            return {'before':body['before'],'after':body['after'],
                    'decision_changes':decision_changes(before,after),
                    'metadata_before':before['metadata'],'metadata_after':after['metadata'],
                    'added':sorted(right.keys()-left.keys()),'removed':sorted(left.keys()-right.keys()),
                    'changed':sorted(k for k in left.keys()&right.keys() if left[k]!=right[k]),
                    'review_required':[e['id'] for e in after['entries'] if e['status'] in ('pending','insufficient')],
                    'historical_operations':self.store.historical_operation_ids(key,body['after']),
                    'notice':'Review impact is conservative; all source changes require renewed review.'}
        revision=body['revision']
        if type(revision) is not int or revision<1:raise ValueError('Invalid revision')
        row=self.store.get(key,revision);draft=row['draft']
        if action=='withdraw_pending':
            kind=body['kind']
            fields={'fixed_case':{'case_id'},'replacement_proposal':{'proposal'},
                    'source_lookup':{'selection'},'model_suggestions':{'draft_digest'},'question':{'question'}}
            if draft.get('adapter')=='registered-database-1':
                fields.update({name:required-{'id','revision','request_key'}
                               for name,required in {**DOCUMENT_ACTIONS,**QUERY_ACTIONS,**REASONING_ACTIONS,**SCOPE_ACTIONS}.items()
                               if 'request_key' in required})
            if not isinstance(kind,str) or kind not in fields or not isinstance(body['request'],dict) or set(body['request'])!=fields[kind]:
                raise ValueError('Invalid pending request binding')
            if kind=='model_suggestions' and body['request']['draft_digest']!=row['digest']:
                raise ValueError('Pending generation must bind the original draft')
            operation,created=self.store.begin(key,revision,body['request_key'],kind,body['request'],cancel_unstarted=True)
            saved=self.store.operation(key,operation['id'])
            return {'operation':saved,'withdrawn':created,'reused':not created}
        if action=='local_reasoning':
            from .workspace_reasoning import execute
            return execute(self.store,self.local_reasoner,key,revision,body['request_key'],
                           body['asserted_base64'],body['profile'])
        if draft.get('adapter')=='registered-database-1':
            if action == LOCALIZE:
                from .workspace_proposal_language import handle as translate_action
                return translate_action(self,body,row)
            if action in SHAPES_ACTIONS:
                from .workspace_database_shapes_service import handle as shapes_action
                return shapes_action(self,action,body,row)
            if action=='ask':
                from .workspace_database_question_service import handle as question_action
                return question_action(self,body,row)
            if action in SCOPE_ACTIONS:
                from .workspace_question_scope import handle as scope_action
                return scope_action(self,action,body,row)
            if action in REASONING_ACTIONS:
                from .workspace_query_reasoning_service import handle as reasoning_action
                return reasoning_action(self,action,body,row)
            if action in QUERY_ACTIONS:
                from .workspace_query_service import handle as query_action
                return query_action(self,action,body,row)
            if action in DOCUMENT_ACTIONS:
                from .workspace_document_service import handle as document_action
                return document_action(self.store,self.source_documents,self._database(),action,body,row)
            if action=='extension_import':
                # A retained proposal is not an adopted or executable mapping.
                draft=self._database().restore(draft)
            elif action in ('extension_review','extension_review_batch'):
                # Validation occurs inside the reserved review attempt so a
                # failed binding remains inspectable without a partial write.
                pass
            else:
                return self._database_action(action,body,row)
        if action=='extension_review_batch':
            from .workspace_extension_review import review
            return review(self.store,key,revision,body['request_key'],
                          {'operation_id':body['operation_id'],'decisions':body['decisions']},
                          database_adapter=self.database_adapter)
        if action=='extension_review':
            from .workspace_extension_review import review, REVIEW_FIELDS
            return review(self.store,key,revision,body['request_key'],{k:body[k] for k in REVIEW_FIELDS},
                          database_adapter=self.database_adapter)
        if action=='extension_import':
            import base64
            import binascii
            from .workspace_extensions import import_auto_ontology
            encoded=body['raw_base64']
            if not isinstance(encoded,str) or len(encoded)>1_333_336:
                raise ValueError('External export exceeds the 1 MB input boundary')
            operation,created=self.store.begin(key,revision,body['request_key'],
                'extension_import',{'raw_base64':encoded,'base_digest':row['digest']})
            if created:
                try:
                    raw=base64.b64decode(encoded,validate=True)
                    result=import_auto_ontology(raw,base_workspace_digest=row['digest'],
                        source_hashes={s['name']:s['sha256'] for s in draft['sources']})
                    self.store.finish(operation['id'],'completed',result=result)
                except (ValueError,TypeError,binascii.Error) as exc:
                    self.store.finish(operation['id'],'failed',error=str(exc)[:1000])
            # This is a saved proposal, not a restored or approved workspace.
            return {'operation':self.store.operation(key,operation['id']),'reused':not created}
        if action=='save_review_buffer':
            content=body['content']
            if not isinstance(content,dict) or set(content)-{'comparisons'}!={'entries','policies'}:
                raise ValueError('Invalid review buffer')
            entries=content['entries'];policies=content['policies']
            if not isinstance(entries,list) or len(entries)>len(draft['entries']) or not isinstance(policies,list) or len(policies)>30:
                raise ValueError('Invalid review buffer entries')
            known={e['id']:e for e in draft['entries']};seen=set()
            for entry in entries:
                if not isinstance(entry,dict) or set(entry)-{'temporal'}!={'entry_id','status','target','note','interpretation'}:
                    raise ValueError('Invalid buffered entry')
                if not isinstance(entry['entry_id'],str) or entry['entry_id'] not in known or entry['entry_id'] in seen:
                    raise ValueError('Unknown or duplicate buffered entry')
                if 'temporal' in entry:
                    from . import policy_dates
                    source_entry=known[entry['entry_id']]
                    if source_entry['kind']!='policy':raise ValueError('Date roles require policy source')
                    policy_dates.validate(entry['temporal'],source_entry['source']['text'])
                seen.add(entry['entry_id'])
                if entry['status'] not in ('pending','approved','excluded','insufficient') or not all(isinstance(entry[k],str) and len(entry[k])<=4000 for k in ('note','interpretation')):
                    raise ValueError('Invalid buffered decision text')
                target=entry['target']
                if (known[entry['entry_id']]['kind']=='relation')!=isinstance(target,dict):
                    raise ValueError('Buffered target kind does not match source entry')
                if not (isinstance(target,str) and len(target)<=200 or isinstance(target,dict) and set(target)=={'file','column','sha256'} and all(isinstance(v,str) and len(v)<=2000 for v in target.values())):
                    raise ValueError('Invalid buffered target')
            groups={g['target']:g for g in workspace_policy.groups(draft)};seen=set()
            for policy in policies:
                if not isinstance(policy,dict) or set(policy)!={'target','selected_id','rationale'} or not all(isinstance(v,str) for v in policy.values()):
                    raise ValueError('Invalid buffered policy')
                if policy['target'] not in groups or policy['target'] in seen or len(policy['rationale'])>3500 or policy['selected_id'] not in ['']+[e['id'] for e in groups[policy['target']]['entries']]:
                    raise ValueError('Invalid buffered policy candidate')
                seen.add(policy['target'])
            comparisons=content.get('comparisons',[])
            if not isinstance(comparisons,list) or len(comparisons)>30:
                raise ValueError('Invalid buffered comparisons')
            seen=set()
            for comparison in comparisons:
                if not isinstance(comparison,dict) or set(comparison)!={'entry_id','binding','decision','basis','rationale'}:
                    raise ValueError('Invalid buffered comparison')
                entry_id=comparison['entry_id']
                if not isinstance(entry_id,str) or entry_id in seen:
                    raise ValueError('Duplicate or invalid buffered comparison')
                seen.add(entry_id)
                record={k:v for k,v in comparison.items() if k!='entry_id'}
                if not isinstance(record['rationale'],str) or len(record['rationale'])>3500:
                    raise ValueError('Invalid buffered comparison rationale')
                policy_agreement.validate({**record,'rationale':record['rationale'].strip() or 'Unfinished draft'})
                if policy_agreement.status(draft,entry_id)['binding']!=record['binding']:
                    raise ValueError('Buffered comparison inputs changed; reopen the comparison')
            return self.store.save_review_buffer(key,revision,body['generation'],content)
        if action=='ask':
            question=body['question']
            if not isinstance(question,str) or not 1<=len(question.strip())<=6000:
                raise ValueError('Question must contain 1..6000 characters')
            operation,created=self.store.begin(key,revision,body['request_key'],'question',{'question':question})
            if created:
                trace={'mode':'workspace_question','question':question,'evidence':[],'answer':None,
                       'workspace':{'id':key,'revision':revision,'draft_digest':row['digest']}}
                def checkpoint(value):
                    trace.update(value)
                    self.store.checkpoint(operation['id'],trace)
                    if self.store.cancel_requested(operation['id']):raise OperationCancelled()
                def model_call(messages):
                    if self.store.cancel_requested(operation['id']):raise OperationCancelled()
                    return self.question_gateway.call(operation['id'],messages)
                try:
                    if self.question_gateway is None:raise ValueError('Question model is not enabled on this server')
                    trace['model']=self.question_gateway.config['model']
                    workspace_question.ask(draft,question,model_call,checkpoint)
                    self.store.finish(operation['id'],'completed',result=trace)
                except OperationCancelled:
                    self.store.finish(operation['id'],'cancelled',result=trace,error='Cancellation requested; retained received evidence. In-flight requests may be charged.')
                except Exception as exc:
                    error=str(exc)[:1000] if isinstance(exc,(ValueError,KeyError,TypeError)) else 'Question execution failed; original partial evidence retained'
                    try:
                        self.store.finish(operation['id'],'failed',result=trace,error=error)
                    except ValueError:
                        self.store.fail_preserving_checkpoint(operation['id'],
                            ('Latest trace could not be persisted; only the last committed checkpoint is retained. '+error)[:1000])
            return {'operation':self.store.operation(key,operation['id']),'reused':not created}
        if action=='compare_policy':
            revised=policy_agreement.review(draft,body['entry_id'],body['binding'],body['decision'],body['basis'],body['rationale'])
            self.store.save(key,revised,revision)
            return self.view(key)
        if action=='resolve_policy':
            revised=workspace_policy.resolve(draft,body['target'],body['selected_id'],body['rationale'])
            self.store.save(key,revised,revision)
            return self.view(key)
        if action=='suggest':
            operation,created=self.store.begin(key,revision,body['request_key'],'model_suggestions',{'draft_digest':row['digest']})
            if created:
                try:
                    if self.proposal_gateway is None:raise ValueError('Model proposals are not enabled on this server')
                    if draft['adapter']!=p.ADAPTER:raise ValueError('Model proposals currently support commerce only')
                    gateway=self.proposal_gateway
                    def proposal_call(messages):
                        if self.store.cancel_requested(operation['id']):raise OperationCancelled()
                        return gateway.call(operation['id'],messages)
                    generator=ModelProposalGenerator(proposal_call,gateway.config['model'])
                    generated=p.create([{'name':s['name'],'content':s['content']} for s in draft['sources']],
                                       draft['metadata'],generator=generator,adapter=draft['adapter'])
                    # Store the proposed replacement separately. Never overwrite
                    # current human decisions merely because a provider replied.
                    self.store.finish(operation['id'],'completed',result={'draft':generated,
                        'base_digest':row['digest'],'model':gateway.config['model'],
                        'notice':'Proposed draft only; explicit adoption required; all decisions pending'})
                except OperationCancelled:
                    self.store.finish(operation['id'],'cancelled',error='Cancellation requested before the next model call.')
                except (ValueError,RuntimeError) as exc:
                    self.store.finish(operation['id'],'failed',error=str(exc)[:1000])
                except Exception:
                    self.store.finish(operation['id'],'failed',error='Proposal generation failed; inspect retained gateway ledger before retry')
                    raise
            return {'operation':self.store.operation(key,operation['id']),'reused':not created}
        if action=='adopt_suggestions':
            operation=self.store.operation(key,body['operation_id'])
            if (not operation or operation['kind']!='model_suggestions' or operation['state']!='completed' or
                    operation['revision']!=revision or operation['result']['base_digest']!=row['digest']):
                raise ValueError('Completed proposals must match the current source/review revision')
            generated=p.restore_draft(operation['result']['draft'])
            self.store.save(key,generated,revision)
            return self.view(key)
        if action=='export':
            # Working export deliberately permits pending entries and is not executable.
            return {'format':'workspace-draft-1','workspace_id':key,'revision':revision,
                    'draft':draft,'digest':row['digest'],'review_resolved':all(e['status'] in ('approved','excluded') for e in draft['entries'])}
        if action=='add_relation':
            draft=p.add_relation(draft,body['source'],body['target'],body['reason'])
            self.store.save(key,draft,revision)
            return self.view(key)
        if action in ('change','refresh'):
            if action=='change':
                decisions=body['decisions']
                if not isinstance(decisions,list) or not 1<=len(decisions)<=p.MAX_ENTRIES:raise ValueError('Provide a bounded decision group')
                if any(not isinstance(d,dict) or set(d)-{'temporal'}!={'entry_id','status','target','note','interpretation'} for d in decisions):
                    raise ValueError('Invalid decision fields')
                if len({d['entry_id'] for d in decisions})!=len(decisions):raise ValueError('Duplicate decision entry')
                for d in decisions:draft=p.change(draft,**d)
            else:
                # Validate uploads even for a no-op. Order is presentation only;
                # exact byte hashes and names define this source revision.
                incoming=inspect_sources(body['files'])
                previous={s['name']:s['sha256'] for s in draft['sources']}
                uploaded={s['name']:s['sha256'] for s in incoming}
                metadata=body.get('metadata',draft['metadata'])
                if metadata is None:raise ValueError('Snapshot metadata must be an object')
                if previous!=uploaded or metadata!=draft['metadata']:
                    draft=p.refresh(draft,body['files'],metadata=metadata,
                                    generator=AdvisoryGenerator() if draft['adapter']==p.ADAPTER else None)
            self.store.save(key,draft,revision)
            return self.view(key)
        if action in ('execute','propose','lookup'):
            if action=='execute':
                if not isinstance(body['case_id'],str) or len(body['case_id'])>120:raise ValueError('Invalid case ID')
                kind,request='fixed_case',{'case_id':body['case_id']}
            elif action=='propose':
                kind,request='replacement_proposal',{'proposal':body['proposal']}
            else:
                kind,request='source_lookup',{'selection':body['selection']}
            operation,created=self.store.begin(key,revision,body['request_key'],kind,request)
            if created:
                try:
                    if action in ('execute','propose'):workspace_policy.require_ready(draft)
                    result=((workspace_relations.execute(draft,body['selection'])
                             if isinstance(body['selection'],dict) and 'relation_id' in body['selection']
                             else workspace_lookup.execute(draft,body['selection'])) if action=='lookup' else
                            p.execute_proposal(draft,body['proposal']) if action=='propose'
                            else p.execute(p.freeze(draft),body['case_id']))
                    result['workspace']={'id':key,'revision':revision,'draft_digest':row['digest']}
                    self.store.finish(operation['id'],'completed',result=result)
                except (ValueError,KeyError,TypeError) as exc:
                    self.store.finish(operation['id'],'failed',error=str(exc)[:1000])
                except Exception:
                    self.store.finish(operation['id'],'failed',error='Local execution failed; inspect before retry')
                    raise
            return {'operation':self.store.operation(key,operation['id']),
                    'reused':not created}
