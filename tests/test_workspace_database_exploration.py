"""Scripted saved-source exploration, without a model or source DB connection."""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from apps.factory_lab import workspace_database_question as coordinator
from apps.factory_lab import workspace_database_question_service as service_module


DESCRIPTOR = {'name': 'explore_repository', 'parameters': {}}
EXPLORE = {'tool': 'explore_repository', 'arguments': {'action': 'overview'}}
FINAL = {'answer': 'Saved schema only.', 'citations': ['e1'], 'unresolved': []}


class Script:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.messages = []
        self.executions = []
        self.explorations = []
        self.saved = []

    def call(self, messages):
        self.messages.append(deepcopy(messages))
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        return {'content': json.dumps(reply)}

    def execute(self, *args):
        self.executions.append(args)
        return {'rows': []}

    def explore(self, arguments):
        self.explorations.append(arguments)
        return {'mode': 'repository_exploration', 'items': [{'source': 'saved table'}]}

    def run(self, catalog=None, **kwargs):
        return coordinator.ask('Describe available fields', catalog=catalog or [],
            call=self.call, execute=self.execute, checkpoint=self.saved.append,
            exploration_catalog=DESCRIPTOR, explore=self.explore, **kwargs)


def plan(calls=None, followup=False):
    return {'calls': calls if calls is not None else [EXPLORE],
            'unresolved': [], 'needs_followup': followup}


def test_empty_approval_catalog_explores_pending_metadata():
    script = Script([plan(), FINAL])
    result = script.run()
    assert len(script.messages) == 2
    assert script.executions == []
    assert result['mode'] == 'database_question'
    assert result['evidence'][0]['tool'] == 'explore_repository'
    assert result['citations'] == ['e1']


def test_three_rounds_receive_previous_evidence_and_then_answer():
    script = Script([plan(followup=True), plan(followup=True), plan(followup=True), FINAL])
    result = script.run()
    assert len(script.messages) == 4
    assert len(result['plans']) == 3
    assert len(result['evidence']) == 3
    second = json.loads(script.messages[1][1]['content'])
    assert second['evidence'][0]['id'] == 'e1'
    assert second['remaining_tools'] == 7
    assert 'limit reached' in result['unresolved'][-1]


def test_eight_tools_stop_requested_followup():
    script = Script([plan([EXPLORE] * 4, True), plan([EXPLORE] * 4, True), FINAL])
    result = script.run()
    assert len(script.messages) == 3
    assert len(result['evidence']) == 8
    assert len({e['id'] for e in result['evidence']}) == 8


def test_exceeding_remaining_tool_budget_preserves_plan_without_execution():
    script = Script([plan([EXPLORE] * 4, True), plan([EXPLORE] * 3, True), plan([EXPLORE] * 2)])
    with pytest.raises(ValueError, match='Invalid bounded'):
        script.run()
    assert len(script.explorations) == 7
    assert len(script.saved[-1]['plans']) == 3


def test_mixed_plan_keeps_query_validator_before_any_tool_execution():
    catalog = [{'approval_operation_id': 'approved', 'parameters': {'count': 'integer'}}]
    bad = {'approval_operation_id': 'approved', 'parameters': {'count': True}}
    script = Script([plan([EXPLORE, bad])])
    with pytest.raises(ValueError, match='approved type'):
        script.run(catalog)
    assert script.executions == script.explorations == []


def test_unknown_tool_and_nonboolean_followup_are_rejected():
    for bad in [plan([{'tool': 'sql', 'arguments': {}}]), {**plan(), 'needs_followup': 'yes'}]:
        script = Script([bad])
        with pytest.raises(ValueError):
            script.run()
        assert script.executions == script.explorations == []


def test_failed_exploration_is_saved_without_retry_or_absence_claim():
    script = Script([plan()])
    def failed(arguments):
        raise ValueError('Unsupported exploration action')
    script.explore = failed
    result = script.run()
    assert result['evidence'][0]['state'] == 'failed'
    assert result['citations'] == []
    assert len(script.messages) == 1
    assert 'absent' not in result['answer']


def test_legacy_empty_catalog_still_skips_provider():
    script = Script([])
    result = coordinator.ask('Describe schema', catalog=[], call=script.call,
        execute=script.execute, checkpoint=script.saved.append)
    assert script.messages == []
    assert result['phase'] == 'completed'


def test_followup_provider_failure_preserves_previous_evidence_without_retry():
    script = Script([plan(followup=True), RuntimeError('Provider failed')])
    with pytest.raises(RuntimeError):
        script.run()
    assert len(script.messages) == 2
    assert script.saved[-1]['evidence'][0]['state'] == 'completed'


def test_service_binds_saved_draft_and_checks_revision(monkeypatch):
    row = {'id': 'workspace', 'revision': 1, 'digest': 'saved', 'draft': {'entries': []}}
    saved = {'id': 'parent', 'state': 'running'}
    class Store:
        def get(self, ident): return deepcopy(row)
        def begin(self, *args): return deepcopy(saved), True
        def checkpoint(self, ident, trace): saved['result'] = deepcopy(trace)
        def finish(self, ident, state, **kwargs): saved.update(state=state, **kwargs)
        def operation(self, *args): return deepcopy(saved)
    gateway = SimpleNamespace(config={})
    service = SimpleNamespace(store=Store(), question_gateway=gateway, _database=lambda:None)
    monkeypatch.setattr('apps.factory_lab.workspace_source_query.catalog',lambda *args:{'name':'query_source','enabled':False,'fields':[]})
    monkeypatch.setattr(service_module, 'cancellation_callback', lambda *args: lambda: False)
    monkeypatch.setattr(service_module, 'build_catalog', lambda *args: [])
    observed = []
    monkeypatch.setattr(service_module.exploration, 'execute',
                        lambda draft, args: observed.append((draft, args)) or {'saved': True})
    def ask(question, **kwargs):
        assert kwargs['catalog'] == []
        assert kwargs['exploration_catalog']['name'] == 'explore_repository'
        result = kwargs['explore']({'action': 'overview'})
        assert result['saved'] is True
        assert result['available_tools'][1]['descriptor_count'] == 0
        assert result['available_tools'][1]['approval_operation_ids'] == []
        service.store.get = lambda ident: {**row, 'revision': 2}
        with pytest.raises(ValueError, match='current workspace revision'):
            kwargs['explore']({'action': 'overview'})
    monkeypatch.setattr(service_module.coordinator, 'ask', ask)
    outcome = service_module.handle(service, {'question': 'Describe schema', 'request_key': 'one'}, row)
    assert outcome['operation']['state'] == 'failed'
    assert 'current workspace revision' in outcome['operation']['error']
    assert observed == [(row['draft'], {'action': 'overview'})]
    assert outcome['operation']['result']['child_operations'] == []


@pytest.mark.parametrize('mutation', ['revision', 'archived'])
def test_final_response_revision_change_is_failed_and_retained(monkeypatch, mutation):
    row = {'id':'workspace','revision':1,'digest':'saved','draft':{'sources':[],'entries':[]}}
    current=deepcopy(row);saved={'id':'parent','state':'running'}
    class Store:
        def get(self, ident):return deepcopy(current)
        def begin(self,*args):return deepcopy(saved),True
        def checkpoint(self,ident,trace):saved['result']=deepcopy(trace)
        def finish(self,ident,state,**kwargs):saved.update(state=state,**kwargs)
        def operation(self,*args):return deepcopy(saved)
    calls=[]
    def call(ident,messages):
        calls.append(messages)
        if len(calls)==1:
            value={'calls':[{'tool':'explore_repository','arguments':{'action':'overview'}}],'unresolved':[]}
        else:
            current[mutation]=2 if mutation=='revision' else True
            value={'answer':'Received but invalidated','citations':['e1'],'unresolved':[]}
        return {'content':json.dumps(value)}
    svc=SimpleNamespace(store=Store(),question_gateway=SimpleNamespace(config={},call=call),_database=lambda:None)
    monkeypatch.setattr('apps.factory_lab.workspace_source_query.catalog',lambda *args:{'name':'query_source','enabled':False,'fields':[]})
    monkeypatch.setattr(service_module,'cancellation_callback',lambda *args:lambda:False)
    monkeypatch.setattr(service_module,'build_catalog',lambda *args:[])
    outcome=service_module.handle(svc,{'question':'Describe schema','request_key':'race'},row)['operation']
    assert outcome['state']=='failed'
    assert len(calls)==2
    assert outcome['result']['evidence'][0]['state']=='completed'
    assert 'Received but invalidated' in outcome['result']['response_after_revision_change']['content']


def test_db_resolution_keeps_original_plan_and_does_not_validate_truth():
    first=plan();first['unresolved']=['Describe fields','Execute refund']
    final={**FINAL,'unresolved':['Execute refund'],'resolved_requirements':[{'requirement':'Describe fields','citations':['e1'],'explanation':'Model claims schema satisfies request'}]}
    result=Script([first,final]).run()
    assert result['unresolved']==['Execute refund']
    assert result['planning_unresolved']==first['unresolved']
    assert result['plans'][0]['unresolved']==first['unresolved']
    assert result['resolution_authority']=='model_interpretation_not_verified_truth'
