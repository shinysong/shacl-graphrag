"""Offline injected transport only; fixture prices are not approved live prices."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import hashlib
import fcntl
from pathlib import Path
import sqlite3
import tempfile
import unittest

from apps.factory_lab.extension_gateway import Config, Denied, Gateway, Model, Response


CHAT = '/v1/chat/completions'
EMBED = '/v1/embeddings'


def config(**kwargs):
    model = Model('openai/auto-ontology-reasoning', 'vendor/chat', 'chat',
                  'provider', 10, 20, 50000, 8192, 'OFFLINE FIXTURE ONLY')
    embedding = replace(model, alias='openai/auto-ontology-embedding', actual_id='vendor/embed',
                        kind='embedding', output_nanodollars_per_token=0, max_output_tokens=0)
    return replace(Config((model, embedding), 20, 1_000_000, 10_000_000,
                          2000, 10, 20000, 1000000), **kwargs)


def chat(**kwargs):
    return dict(model='openai/auto-ontology-reasoning', messages=[{'role':'user', 'content':'hello'}],
                max_tokens=100, **kwargs)


class GatewayTests(unittest.TestCase):
    def test_settled_success_releases_unused_hold_but_keeps_raw_reservations(self):
        cfg=config(reservation_accounting='settled',total_nanodollars=1_500_000)
        g=self.gateway(cfg,transport=lambda *a:Response(200,b'{"choices":[],"usage":{"cost":0.0001}}'))
        for _ in range(6):g.handle(CHAT,chat())
        self.assertEqual(self.counts(),(6,6_000_000))
        with self.assertRaises(Denied):g.handle(CHAT,chat())
        with sqlite3.connect(self.path) as db:
            from apps.factory_lab.extension_gateway import ledger_totals
            self.assertEqual(ledger_totals(db,'settled')['used'],600_000)
        # Reopening preserves actual charges and does not replenish allowance.
        reopened=self.gateway(cfg,transport=lambda *a:self.fail('Budget must reject before transport'))
        with self.assertRaises(Denied):reopened.handle(CHAT,chat())

    def test_settled_failure_missing_invalid_or_excess_cost_is_not_released(self):
        bad=(b'{"choices":[],"usage":{}}',b'{"usage":{"cost":null}}',b'{"usage":{"cost":true}}',
             b'{"usage":{"cost":-1}}',b'{"usage":{"cost":1}}')
        for i,body in enumerate(bad):
            with self.subTest(i=i):
                ledger=Path(self.temp.name)/f'bad-{i}.sqlite'
                g=Gateway(ledger,config(reservation_accounting='settled',total_nanodollars=1_000_000),
                    'operator-secret',lambda *a:Response(200,body),lambda:1000)
                with self.assertRaises(Denied):g.handle(CHAT,chat())
                with self.assertRaises(Denied):g.handle(CHAT,chat())
                with sqlite3.connect(ledger) as db:self.assertEqual(db.execute('SELECT count(*) FROM attempts').fetchone()[0],1)

    def test_settled_concurrent_holds_cannot_oversubscribe(self):
        import threading
        started=threading.Event();release=threading.Event();sent=[]
        def transport(*a):
            sent.append(True);started.set();release.wait(2)
            return Response(200,b'{"usage":{"cost":0.0001}}')
        g=self.gateway(config(reservation_accounting='settled',total_nanodollars=1_000_000),transport)
        with ThreadPoolExecutor(max_workers=2) as pool:
            future=pool.submit(g.handle,CHAT,chat());self.assertTrue(started.wait(1))
            with self.assertRaises(Denied):g.handle(CHAT,chat())
            release.set();future.result()
        self.assertEqual(len(sent),1)

    def test_settled_authorized_reset_carries_actual_cost_not_old_unused_holds(self):
        old=self.gateway(transport=lambda *a:Response(200,b'{"usage":{"cost":0.0001}}'))
        old.handle(CHAT,chat());old.handle(CHAT,chat())
        old_hash=hashlib.sha256(self.path.read_bytes()).hexdigest()
        cfg=config(reservation_accounting='settled',inherited_attempts=2,inherited_reserved_nanodollars=200_000,
            prior_ledger_path=str(self.path),prior_ledger_sha256=old_hash,
            campaign_lock_path=str(Path(self.temp.name)/'reset.lock'),total_nanodollars=1_500_000)
        new=Gateway(Path(self.temp.name)/'reset.sqlite',cfg,'operator-secret',
            lambda *a:Response(200,b'{"usage":{"cost":0.0001}}'),lambda:1000)
        try:
            for _ in range(4):new.handle(CHAT,chat())
            with self.assertRaises(Denied):new.handle(CHAT,chat())
            self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(),old_hash)
        finally:new.close()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'ledger.sqlite'
        self.sent = []

    def tearDown(self):
        self.temp.cleanup()

    def transport(self, route, body, secret, timeout, max_bytes):
        self.sent.append((route, json.loads(body), secret))
        with sqlite3.connect(self.path) as db:
            assert db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0] > 0
        return Response(200, b'{"choices":[],"usage":{"prompt_tokens":3}}')

    def gateway(self, cfg=None, transport=None, clock=None):
        return Gateway(self.path, cfg or config(), 'operator-secret', transport or self.transport,
                       clock or (lambda: 1000))

    def counts(self):
        with sqlite3.connect(self.path) as db:
            return db.execute('SELECT COUNT(*),COALESCE(SUM(reserved),0) FROM attempts').fetchone()

    def test_concurrent_budget_shared_restart_and_retries(self):
        g = self.gateway()
        def send(_):
            try:
                g.handle(CHAT, chat())
                return True
            except Denied:
                return False
        with ThreadPoolExecutor(max_workers=12) as pool:
            self.assertEqual(sum(pool.map(send, range(40))), 10)
        self.assertEqual(self.counts(), (10, 10_000_000))
        with self.assertRaises(Denied):
            self.gateway().handle(CHAT, chat())
        self.assertEqual(len(self.sent), 10)

    def test_captured_pinned_upstream_sdk_shapes(self):
        # Captured 2026-11-19 from actual upstream ee42eff638ebd136c1c4fe4ab290785f912bb4bc
        # get_llm_client(...).with_structured_output(Pydantic), get_non_reasoning_llm_client,
        # and embed_texts(..., input_type="passage", retries=0), against localhost only.
        # langchain-openai 1.3.4 / openai 2.44.0 / httpx 0.28.1. No actual model output.
        # The SDK converts upstream max_tokens to max_completion_tokens; n is omitted.
        cfg = config()
        cfg = replace(cfg, models=cfg.models + (replace(cfg.models[0],
            alias='openai/auto-ontology-nonreasoning'),))
        g = self.gateway(cfg)
        reasoning = {
            'messages': [{'content': 'fixture question', 'role': 'user'}],
            'model': 'openai/auto-ontology-reasoning', 'max_completion_tokens': 1024,
            'response_format': {'type': 'json_schema', 'json_schema': {
                'schema': {'properties': {'answer': {'title': 'Answer', 'type': 'string'}},
                           'required': ['answer'], 'title': 'Answer', 'type': 'object',
                           'additionalProperties': False}, 'name': 'Answer', 'strict': True}},
            'stream': False}
        nonreasoning = {'messages': [{'content': 'fixture question', 'role': 'user'}],
                       'model': 'openai/auto-ontology-nonreasoning',
                       'max_completion_tokens': 4096, 'stream': False}
        g.handle(CHAT, reasoning)
        g.handle(CHAT, nonreasoning)
        embedding = {'input': ['fixture passage'], 'model': 'openai/auto-ontology-embedding',
                     'encoding_format': 'float', 'input_type': 'passage',
                     'truncate': 'END', 'modality': 'text'}
        _, original, wire = g._prepare(EMBED, embedding)
        self.assertEqual(json.loads(original), embedding)
        self.assertEqual(json.loads(wire)['dimensions'], 2048)
        for bad in ({**reasoning, 'n': 2}, {**reasoning, 'max_completion_tokens': None},
                    {**reasoning, 'max_completion_tokens': 8193}):
            with self.assertRaises(Denied):
                g.handle(CHAT, bad)
        self.assertEqual(len(self.sent), 2)

    def test_call_cap(self):
        g = self.gateway(config(call_cap=1))
        g.handle(CHAT, chat())
        with self.assertRaises(Denied):
            g.handle(CHAT, chat())

    def test_failed_attempt_keeps_reservation_and_captures_response(self):
        g = self.gateway(transport=lambda *args: Response(429, b'{"error":"rate limit", "usage":null}'))
        for _ in range(2):
            with self.assertRaises(Denied):
                g.handle(CHAT, chat())
        self.assertEqual(self.counts(), (2, 2_000_000))
        with sqlite3.connect(self.path) as db:
            rows = db.execute('SELECT status,response,error FROM completions').fetchall()
        self.assertEqual(rows[0], (429, b'{"error":"rate limit", "usage":null}', 'Denied'))

    def test_exception_not_retried_or_secret_logged(self):
        calls = []
        def failure(*args):
            calls.append(1)
            raise OSError('operator-secret')
        with self.assertRaises(Denied):
            self.gateway(transport=failure).handle(CHAT, chat())
        self.assertEqual(calls, [1])
        self.assertEqual(self.counts()[0], 1)
        self.assertNotIn(b'operator-secret', self.path.read_bytes())

    def test_route_alias_output_and_request_settings_rejected(self):
        g = self.gateway()
        bad = [('/v1/models', chat()), (CHAT, {**chat(), 'model':'vendor/chat'}),
               (EMBED, chat()), (CHAT, {**chat(), 'max_tokens':None}),
               (CHAT, {**chat(), 'max_tokens':8193}), (CHAT, chat(stream=True)),
               (CHAT, chat(provider={})), (CHAT, chat(n=4)),
               (CHAT, {**chat(), 'messages':[{'role':'user', 'content':[{'type':'image_url'}]}]}),
               (CHAT, {**chat(), 'messages':[{'role':'user', 'content':'x'*20000}]})]
        for route, payload in bad:
            with self.subTest(payload=payload), self.assertRaises(Denied):
                g.handle(route, payload)
        self.assertEqual(self.counts()[0], 0)

    def test_unknown_price_bounds_config_freeze_and_deadline(self):
        cfg = config()
        with self.assertRaises(Denied):
            self.gateway(replace(cfg, models=(replace(cfg.models[0], input_nanodollars_per_token=0),)))
        with self.assertRaises(Denied):
            self.gateway(replace(cfg, total_nanodollars=10_000_000_001))
        self.gateway()
        with self.assertRaises(Denied):
            self.gateway(config(call_cap=100))
        with self.assertRaises(Denied):
            self.gateway(clock=lambda:1991).handle(CHAT, chat())
        self.assertEqual(self.counts()[0], 0)

    def test_conservative_cost_rejection(self):
        with self.assertRaises(Denied):
            self.gateway(config(per_call_nanodollars=100))
        self.assertFalse(self.path.exists())

    def test_embedding_adapter_real_dimensions_and_shared_budget(self):
        def embed(route, body, secret, timeout, max_bytes):
            request = json.loads(body)
            self.assertEqual(request['dimensions'], 2048)
            self.assertNotIn('truncate', request)
            self.assertNotIn('input_type', request)
            self.assertNotIn('modality', request)
            return Response(200, json.dumps({'data':[{'index':0,'embedding':[0.1]*2048}],
                                             'usage':{'prompt_tokens':4}}).encode())
        g = self.gateway(config(call_cap=2), transport=embed)
        payload = dict(model='openai/auto-ontology-embedding', input=['hello'], input_type='passage',
                       truncate='END', modality='text', encoding_format='float')
        g.handle(EMBED, payload)
        self.gateway(config(call_cap=2)).handle(CHAT, chat())
        with self.assertRaises(Denied):
            g.handle(EMBED, payload)
        self.assertEqual(self.counts()[0], 2)

    def test_wrong_dimension_is_failed_paid_attempt(self):
        g = self.gateway(transport=lambda *args: Response(200, b'{"data":[{"index":0,"embedding":[1]}]}'))
        with self.assertRaises(Denied):
            g.handle(EMBED, dict(model='openai/auto-ontology-embedding', input='hello'))
        self.assertEqual(self.counts()[0], 1)

    def test_immutable_records_and_response_usage(self):
        self.gateway().handle(CHAT, chat())
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT usage FROM completions').fetchone()[0], '{"prompt_tokens":3}')
            for sql in ('DELETE FROM attempts', 'UPDATE configuration SET value="{}"', 'DELETE FROM completions'):
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute(sql)
        request = self.sent[0][1]
        self.assertEqual(request['model'], 'vendor/chat')
        self.assertEqual(request['provider']['allow_fallbacks'], False)

    def test_full_context_model_reservations_and_live_price_ceiling(self):
        cfg = config()
        chat_model = replace(cfg.models[0], input_nanodollars_per_token=825,
            output_nanodollars_per_token=4125, max_input_tokens=1048576,
            billing_output_tokens=65536, reservation_nanodollars=1_140_000_000)
        embed_model = replace(cfg.models[1], input_nanodollars_per_token=130,
            max_input_tokens=8192, reservation_nanodollars=2_000_000)
        cfg = replace(cfg, models=(chat_model,embed_model), call_cap=100,
            total_nanodollars=10_000_000_000, per_call_nanodollars=1_140_000_000)
        def transport(route,wire,*args):
            body=json.loads(wire)
            price=body['provider']['max_price']
            self.assertEqual(price['request'],0)
            self.assertEqual(body['provider']['only'],['provider'])
            self.assertTrue(body['provider']['require_parameters'])
            if route==CHAT:
                self.assertEqual(price,{'prompt':0.825,'completion':4.125,'request':0})
                self.assertEqual(body['max_tokens'],1)
                self.assertNotIn('max_completion_tokens',body)
                return Response(200,b'{"choices":[],"usage":{"cost":0.0001}}')
            self.assertEqual(price['prompt'],0.13)
            return Response(200,json.dumps({'data':[{'index':0,'embedding':[0.1]*2048}]}).encode())
        g=self.gateway(cfg,transport=transport)
        request={**chat(),'max_completion_tokens':1};request.pop('max_tokens')
        for _ in range(8):g.handle(CHAT,request)
        self.assertEqual(self.counts(),(8,9_120_000_000))
        with self.assertRaises(Denied):g.handle(CHAT,request)
        # No refund for cheap actual usage; reserve full input AND output every time.
        for _ in range(92):
            g.handle(EMBED,{'model':embed_model.alias,'input':['one input']})
        self.assertEqual(self.counts(),(100,9_304_000_000))
        with self.assertRaises(Denied):
            g.handle(EMBED,{'model':embed_model.alias,'input':'one input'})
        with sqlite3.connect(self.path) as db:
            original,actual=db.execute('SELECT original,request FROM attempts WHERE id=1').fetchone()
            self.assertEqual(json.loads(original)['max_completion_tokens'],1)
            self.assertEqual(json.loads(actual)['max_tokens'],1)

    def test_embedding_batch_and_billed_server_tools_denied(self):
        g=self.gateway()
        for route,request in (
            (EMBED,{'model':'openai/auto-ontology-embedding','input':['a','b']}),
            (CHAT,chat(tools=[{'type':'web_search'}])),
            (CHAT,chat(tools=[{'type':'function','function':{},'cache_control':{}}])),
            (CHAT,chat(plugins=[{'id':'web'}])),
            (CHAT,chat(cache_control={'type':'ephemeral'})),
            (CHAT,chat(provider={'max_price':{'prompt':999}}))):
            with self.assertRaises(Denied):g.handle(route,request)
        self.assertEqual(self.counts()[0],0)

    def test_carryforward_same_campaign_caps_and_prior_hash(self):
        # Temporary fixtures only: predecessor remains byte-identical after continuation.
        prior=self.gateway()
        prior.handle(CHAT,chat())
        prior.handle(CHAT,chat())
        old_hash=hashlib.sha256(self.path.read_bytes()).hexdigest()
        new_path=Path(self.temp.name)/'continuation.sqlite'
        lock=Path(self.temp.name)/'campaign.lock'
        cfg=replace(config(),inherited_attempts=2,inherited_reserved_nanodollars=2_000_000,
            prior_ledger_path=str(self.path),prior_ledger_sha256=old_hash,campaign_lock_path=str(lock),
            chat_attempt_cap=2,embedding_attempt_cap=1,call_cap=5)
        g=Gateway(new_path,cfg,'operator-secret',self.transport,lambda:1000)
        try:
            g.handle(CHAT,chat())
            g.handle(CHAT,chat())
            with self.assertRaises(Denied):g.handle(CHAT,chat())
            # Both reasoning aliases share one route-level cap; a competing launcher
            # cannot acquire the original campaign lock during this gateway lifetime.
            with lock.open('a') as competing:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(competing,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(),old_hash)
            # Tamper detection uses a fresh check before reservation, not just startup.
            with self.path.open('ab') as out:out.write(b'changed')
            with self.assertRaises(Denied):g.handle(CHAT,chat())
            with sqlite3.connect(new_path) as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0],2)
        finally:g.close()

    def test_inherited_amount_and_attempts_are_not_fresh_allowance(self):
        self.gateway().handle(CHAT,chat())
        cfg=replace(config(),inherited_attempts=1,inherited_reserved_nanodollars=1_000_000,
            prior_ledger_path=str(self.path),prior_ledger_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest(),
            campaign_lock_path=str(Path(self.temp.name)/'campaign.lock'))
        for index,limited in enumerate((replace(cfg,total_nanodollars=1_500_000),replace(cfg,call_cap=1))):
            path=Path(self.temp.name)/f'limited-{index}.sqlite'
            gateway=Gateway(path,limited,'operator-secret',self.transport,lambda:1000)
            try:
                with self.assertRaises(Denied):gateway.handle(CHAT,chat())
                with sqlite3.connect(path) as db:
                    self.assertEqual(db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0],0)
            finally:gateway.close()
        self.assertEqual(len(self.sent),1)

    def test_carryforward_wrong_counts_deadline_or_hash_fails_before_new_ledger(self):
        self.gateway().handle(CHAT,chat())
        original_hash=hashlib.sha256(self.path.read_bytes()).hexdigest()
        cfg=replace(config(),inherited_attempts=1,inherited_reserved_nanodollars=1_000_000,
            prior_ledger_path=str(self.path),prior_ledger_sha256=original_hash,
            campaign_lock_path=str(Path(self.temp.name)/'campaign.lock'))
        for index,bad in enumerate((replace(cfg,inherited_attempts=2),
                                   replace(cfg,deadline_epoch=2001),
                                   replace(cfg,prior_ledger_sha256='0'*64))):
            path=Path(self.temp.name)/f'bad-{index}.sqlite'
            with self.assertRaises(Denied):
                Gateway(path,bad,'operator-secret',self.transport,lambda:1000)
            self.assertFalse(path.exists())

    def test_interrupted_attempt_persists_on_restart(self):
        def interrupt(*args):
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.gateway(config(call_cap=1), transport=interrupt).handle(CHAT, chat())
        with self.assertRaises(Denied):
            self.gateway(config(call_cap=1)).handle(CHAT, chat())
        self.assertEqual(self.counts()[0], 1)


if __name__ == '__main__':
    unittest.main()
