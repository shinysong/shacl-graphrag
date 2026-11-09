"""Durable execution log and atomic, nonrefunded budget reservations."""
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'_workspace/factory-lab-20261109'

def now(): return datetime.now(timezone.utc).isoformat()
def dumps(x): return json.dumps(x,ensure_ascii=False,separators=(',',':'))

class Store:
    def __init__(self,path=None):
        self.path=Path(path or WORK/'state.sqlite');self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.db() as c:
            c.executescript('''CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, created TEXT, status TEXT, config TEXT, answer TEXT);
            CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, at TEXT, kind TEXT, payload TEXT);
            CREATE TABLE IF NOT EXISTS calls(id TEXT PRIMARY KEY, run_id TEXT, at TEXT, reserved TEXT, status TEXT, details TEXT);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);''')
    @contextmanager
    def db(self):
        c=sqlite3.connect(self.path,timeout=20);c.row_factory=sqlite3.Row
        try:
            with c:yield c
        finally:c.close()
    def event(self,rid,kind,payload):
        with self.db() as c:
            c.execute('INSERT INTO events(run_id,at,kind,payload) VALUES(?,?,?,?)',(rid,now(),kind,dumps(payload)))
    def create(self,config):
        rid=uuid.uuid4().hex
        with self.db() as c:c.execute('INSERT INTO runs VALUES(?,?,?,?,?)',(rid,now(),'queued',dumps(config),''))
        self.event(rid,'queued',config);return rid
    def status(self,rid,status,answer=None):
        with self.db() as c:
            c.execute('UPDATE runs SET status=?,answer=COALESCE(?,answer) WHERE id=?',(status,answer,rid))
    def runs(self):
        with self.db() as c: rows=c.execute('SELECT * FROM runs ORDER BY created DESC LIMIT 100').fetchall()
        return [dict(r)|{'config':json.loads(r['config'])} for r in rows]
    def get(self,rid):
        with self.db() as c:r=c.execute('SELECT * FROM runs WHERE id=?',(rid,)).fetchone()
        if r is None:raise KeyError('Unknown run')
        return dict(r)|{'config':json.loads(r['config'])}
    def events(self,rid,after=0):
        with self.db() as c:rows=c.execute('SELECT * FROM events WHERE run_id=? AND seq>? ORDER BY seq',(rid,after)).fetchall()
        return [dict(r)|{'payload':json.loads(r['payload'])} for r in rows]
    def recover(self):
        with self.db() as c:
            ids=[r[0] for r in c.execute("SELECT id FROM runs WHERE status IN ('queued','running')")]
            c.execute("UPDATE runs SET status='interrupted' WHERE status IN ('queued','running')")
        for rid in ids:self.event(rid,'interrupted',{'message':'Server restarted; no automatic retry; reserved calls retained.'})
    def reserve(self,rid,amount,session):
        amount=Decimal(str(amount))
        if not amount.is_finite() or amount<=0:raise ValueError('Invalid reservation')
        if datetime.now(timezone.utc)>=datetime.fromisoformat(session['deadline']):raise RuntimeError('Paid window expired')
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            rows=c.execute('SELECT reserved FROM calls').fetchall()
            spent=sum((Decimal(r[0]) for r in rows),Decimal('0'))
            if len(rows)>=session['max_attempts'] or spent+amount>Decimal(session['max_usd']):raise RuntimeError('Campaign budget exhausted')
            cid=uuid.uuid4().hex
            c.execute('INSERT INTO calls VALUES(?,?,?,?,?,?)',(cid,rid,now(),str(amount),'reserved','{}'))
        return cid
    def settle(self,cid,status,details):
        with self.db() as c:c.execute('UPDATE calls SET status=?,details=? WHERE id=?',(status,dumps(details),cid))
    def budget(self):
        with self.db() as c:rows=c.execute('SELECT * FROM calls').fetchall()
        reserved=sum((Decimal(r['reserved']) for r in rows),Decimal('0'))
        actual=sum((Decimal(str(json.loads(r['details']).get('cost') or 0)) for r in rows),Decimal('0'))
        return {'attempts':len(rows),'reserved_nonrefunded_usd':str(reserved),'reported_usd':str(actual),
                'unresolved':sum(r['status']=='reserved' or json.loads(r['details']).get('cost') is None for r in rows)}
