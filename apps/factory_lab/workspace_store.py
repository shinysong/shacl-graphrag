"""Single-user durable workspace storage, separate from research and paid ledgers.

JSON is stored as data only. Each revision is immutable; archiving never deletes
source/review history. Caller owns semantic validation and runtime execution.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import secrets
import sqlite3

MAX_DOCUMENT_BYTES = 16 * 1024 * 1024
MAX_STORED_BYTES = 256 * 1024 * 1024
MAX_WORKSPACES = 50
MAX_REVISIONS = 500
MAX_OPERATIONS = 500


def encode(value):
    try:
        content=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',', ':'),allow_nan=False)
        if len(content.encode('utf-8'))>MAX_DOCUMENT_BYTES:
            raise ValueError('Workspace document exceeds 16 MiB')
        return content
    except (TypeError,UnicodeError,RecursionError) as exc:
        raise ValueError('Workspace content is not valid JSON') from exc


def require_capacity(db, additional):
    """Logical UTF-8 payload quota, not a claim about SQLite physical disk size."""
    revisions=db.execute('SELECT COALESCE(SUM(length(CAST(content AS BLOB))),0) FROM revisions').fetchone()[0]
    operations=db.execute('SELECT COALESCE(SUM(length(CAST(request AS BLOB))+COALESCE(length(CAST(result AS BLOB)),0)),0) FROM operations').fetchone()[0]
    buffers=db.execute('SELECT COALESCE(SUM(length(CAST(content AS BLOB))),0) FROM review_buffers').fetchone()[0]
    if revisions+operations+buffers+additional>MAX_STORED_BYTES:
        raise ValueError('Workspace payload storage limit reached; export and inspect storage before adding data. Archiving does not free history.')


def now():
    return datetime.now(timezone.utc).isoformat()


class WorkspaceStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connect() as db:
            version=db.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0,1):raise ValueError('Unsupported workspace database version; use matching application')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS workspaces (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, revision INTEGER NOT NULL,
                    archived INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL, updated TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS revisions (
                    workspace TEXT NOT NULL REFERENCES workspaces(id), number INTEGER NOT NULL,
                    content TEXT NOT NULL, digest TEXT NOT NULL, created TEXT NOT NULL,
                    PRIMARY KEY(workspace, number)
                );
                CREATE TABLE IF NOT EXISTS review_buffers (
                    workspace TEXT PRIMARY KEY REFERENCES workspaces(id), revision INTEGER NOT NULL,
                    generation INTEGER NOT NULL, content TEXT NOT NULL, updated TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS operation_cancellations (
                    operation TEXT PRIMARY KEY REFERENCES operations(id), requested TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS operations (
                    id TEXT PRIMARY KEY, workspace TEXT NOT NULL, revision INTEGER NOT NULL,
                    request_key TEXT NOT NULL, kind TEXT NOT NULL, state TEXT NOT NULL,
                    request TEXT NOT NULL, result TEXT, error TEXT, created TEXT NOT NULL, updated TEXT NOT NULL,
                    UNIQUE(workspace, request_key),
                    FOREIGN KEY(workspace, revision) REFERENCES revisions(workspace, number)
                );
            ''')
            db.execute('PRAGMA user_version=1')
        self.path.chmod(0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(self, title, draft):
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 120:
            raise ValueError('Workspace title must be 1..120 characters')
        content = encode(draft)
        key, stamp = secrets.token_hex(16), now()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT COUNT(*) FROM workspaces').fetchone()[0]>=MAX_WORKSPACES:
                raise ValueError('Workspace count limit reached; existing data remains available')
            require_capacity(db,len(content.encode()))
            db.execute('INSERT INTO workspaces VALUES(?,?,1,0,?,?)', (key,title,stamp,stamp))
            db.execute('INSERT INTO revisions VALUES(?,1,?,?,?)', (key,content,sha256(content.encode()).hexdigest(),stamp))
        return self.get(key)

    def get(self, key, revision=None):
        with self.connect() as db:
            row = db.execute('SELECT * FROM workspaces WHERE id=?', (key,)).fetchone()
            if row is None:
                raise ValueError('Unknown workspace')
            version = row['revision'] if revision is None else revision
            saved = db.execute('SELECT * FROM revisions WHERE workspace=? AND number=?', (key,version)).fetchone()
            if saved is None:
                raise ValueError('Unknown workspace revision')
            return {**dict(row), 'revision':version, 'current_revision':row['revision'],
                    'draft':json.loads(saved['content']), 'digest':saved['digest']}

    def list(self, archived=False):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM workspaces WHERE archived=? ORDER BY updated DESC,id', (int(archived),))]

    def save(self, key, draft, expected_revision):
        content, stamp = encode(draft), now()
        digest = sha256(content.encode()).hexdigest()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM workspaces WHERE id=?', (key,)).fetchone()
            if row is None or row['archived']:
                raise ValueError('Workspace missing or archived')
            if row['revision'] != expected_revision:
                raise ValueError('Workspace changed; reload before saving')
            old = db.execute('SELECT digest FROM revisions WHERE workspace=? AND number=?', (key,expected_revision)).fetchone()
            if old['digest'] != digest:
                if expected_revision>=MAX_REVISIONS:
                    raise ValueError('Workspace revision limit reached; export before starting a new workspace')
                require_capacity(db,len(content.encode()))
                version = expected_revision + 1
                db.execute('INSERT INTO revisions VALUES(?,?,?,?,?)', (key,version,content,digest,stamp))
                db.execute('UPDATE workspaces SET revision=?,updated=? WHERE id=?', (version,stamp,key))
        return self.get(key)

    def archive(self, key, archived=True):
        with self.connect() as db:
            if not db.execute('UPDATE workspaces SET archived=?,updated=? WHERE id=?', (int(archived),now(),key)).rowcount:
                raise ValueError('Unknown workspace')

    def revisions(self, key):
        self.get(key)
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT number,digest,created FROM revisions WHERE workspace=? ORDER BY number DESC',(key,))]

    def review_buffer(self, key):
        self.get(key)
        with self.connect() as db:
            row=db.execute('SELECT * FROM review_buffers WHERE workspace=?',(key,)).fetchone()
        return {**dict(row),'content':json.loads(row['content'])} if row else None

    def save_review_buffer(self, key, revision, generation, content):
        encoded=encode(content)
        if len(encoded.encode())>262144:raise ValueError('Review buffer exceeds 256 KiB')
        if type(generation) is not int or generation<0:raise ValueError('Invalid review buffer generation')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM workspaces WHERE id=?',(key,)).fetchone()
            if row is None or row['archived'] or row['revision']!=revision:
                raise ValueError('Review buffer requires current active version')
            old=db.execute('SELECT * FROM review_buffers WHERE workspace=?',(key,)).fetchone()
            if (old['generation'] if old else 0)!=generation:
                raise ValueError('Review buffer changed; reload before replacing it')
            require_capacity(db,max(0,len(encoded.encode())-(len(old['content'].encode()) if old else 0)))
            db.execute('INSERT OR REPLACE INTO review_buffers VALUES(?,?,?,?,?)',
                       (key,revision,generation+1,encoded,now()))
        return self.review_buffer(key)

    def operations(self, key):
        self.get(key)
        with self.connect() as db:
            rows = [dict(r) for r in db.execute('SELECT * FROM operations WHERE workspace=? ORDER BY created DESC,id',(key,))]
        for row in rows:
            row['request'] = json.loads(row['request'])
            row['result'] = json.loads(row['result']) if row['result'] is not None else None
        return rows

    def historical_operation_ids(self, key, revision):
        """Metadata-only references for version comparison, never result payloads."""
        with self.connect() as db:
            return [r[0] for r in db.execute(
                'SELECT id FROM operations WHERE workspace=? AND revision!=? ORDER BY created DESC,id',
                (key,revision))]

    def operation_page(self, key, before=None):
        """Newest-first bounded metadata; result/request blobs are never selected."""
        if before is not None and (type(before) is not int or before<1):
            raise ValueError('Invalid history cursor')
        with self.connect() as db:
            if db.execute('SELECT 1 FROM workspaces WHERE id=?',(key,)).fetchone() is None:
                raise ValueError('Unknown workspace')
            total=db.execute('SELECT COUNT(*) FROM operations WHERE workspace=?',(key,)).fetchone()[0]
            rows=[dict(r) for r in db.execute(
                'SELECT rowid AS cursor,id,workspace,revision,kind,state,error,created,updated FROM operations '
                'WHERE workspace=? AND (? IS NULL OR rowid<?) ORDER BY rowid DESC LIMIT 21',
                (key,before,before))]
        more=len(rows)>20
        rows=rows[:20]
        for row in rows:row['summary_only']=True
        return {'operations':rows,'operation_count':total,
                'operations_next':rows[-1]['cursor'] if more else None}

    def progress(self, key, request_key):
        """Read only one committed checkpoint; never reserve or resume work."""
        if not all(isinstance(v,str) and 1<=len(v)<=120 for v in (key,request_key)):
            raise ValueError('Invalid workspace or request key')
        with self.connect() as db:
            found=db.execute('SELECT id,revision,kind,state,result,updated FROM operations WHERE workspace=? AND request_key=?',(key,request_key)).fetchone()
        if found is None:return {'state':'not_recorded','phase':None}
        row=dict(found);result=json.loads(row.pop('result') or '{}')
        row['cancel_requested']=self.cancel_requested(row['id'])
        row['phase']=result.get('phase')
        row['tools_completed']=sum(e.get('state')=='completed' for e in result.get('evidence',[]))
        row['tools_failed']=sum(e.get('state')=='failed' for e in result.get('evidence',[]))
        row['tools_started']=len(result.get('evidence',[]))
        return row

    def request_cancel(self, key, request_key):
        if not all(isinstance(v,str) and 1<=len(v)<=120 for v in (key,request_key)):
            raise ValueError('Invalid workspace or request key')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT id,kind,state FROM operations WHERE workspace=? AND request_key=?',(key,request_key)).fetchone()
            if row is None:raise ValueError('Request is not recorded yet; wait for progress')
            if row['kind'] not in ('question','model_suggestions'):
                raise ValueError('Only model workflows support cooperative cancellation')
            if row['state']=='running':
                db.execute('INSERT OR IGNORE INTO operation_cancellations VALUES(?,?)',(row['id'],now()))
        return self.progress(key,request_key)

    def cancel_requested(self, oid):
        with self.connect() as db:
            return db.execute('SELECT 1 FROM operation_cancellations WHERE operation=?',(oid,)).fetchone() is not None

    def operation(self, key, operation_id):
        """Load one execution, scoped to its workspace, without loading history."""
        with self.connect() as db:
            found = db.execute('SELECT * FROM operations WHERE workspace=? AND id=?',
                               (key, operation_id)).fetchone()
        if found is None:
            raise ValueError('Unknown operation in this workspace')
        row = dict(found)
        row['request'] = json.loads(row['request'])
        row['result'] = json.loads(row['result']) if row['result'] is not None else None
        return row

    def begin(self, key, revision, request_key, kind, request, *, cancel_unstarted=False):
        """Reserve once before work. Reusing a key returns the original attempt.

        A failed/interrupted attempt is never automatically retried. An explicit
        new attempt must use a new request key; no cost reservations are refunded.
        """
        if not all(isinstance(v,str) and 1<=len(v)<=120 for v in (request_key,kind)):
            raise ValueError('Invalid operation identity')
        content = encode(request)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT * FROM operations WHERE workspace=? AND request_key=?', (key,request_key)).fetchone()
            if old:
                if old['revision']!=revision or old['kind']!=kind or old['request']!=content:
                    raise ValueError('Request key already belongs to different input')
                return dict(old), False
            row = db.execute('SELECT * FROM workspaces WHERE id=?', (key,)).fetchone()
            if row is None or not db.execute('SELECT 1 FROM revisions WHERE workspace=? AND number=?',(key,revision)).fetchone():
                raise ValueError('Unknown workspace revision')
            if not cancel_unstarted and (row['archived'] or row['revision']!=revision):
                raise ValueError('Execution requires the current active revision')
            if db.execute('SELECT COUNT(*) FROM operations WHERE workspace=?',(key,)).fetchone()[0]>=MAX_OPERATIONS:
                raise ValueError('Workspace execution limit reached; existing attempts remain available')
            require_capacity(db,len(content.encode()))
            oid, stamp = secrets.token_hex(16), now()
            db.execute('INSERT INTO operations VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                       (oid,key,revision,request_key,kind,'cancelled' if cancel_unstarted else 'running',content,None,
                        'Unstarted request withdrawn; late submissions with this key will not execute' if cancel_unstarted else None,stamp,stamp))
            return dict(db.execute('SELECT * FROM operations WHERE id=?',(oid,)).fetchone()), True

    def checkpoint(self, oid, result):
        """Persist partial evidence before the next external step; never restart it."""
        content=encode(result)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            previous=db.execute("SELECT result FROM operations WHERE id=? AND state='running'",(oid,)).fetchone()
            if previous is None:raise ValueError('Operation missing or already terminal')
            require_capacity(db,max(0,len(content.encode())-len((previous['result'] or '').encode())))
            changed=db.execute("UPDATE operations SET result=?,updated=? WHERE id=? AND state='running'",(content,now(),oid))
            if not changed.rowcount:raise ValueError('Operation missing or already terminal')

    def finish(self, oid, state, result=None, error=None):
        if state not in ('completed','failed','cancelled'):
            raise ValueError('Invalid terminal operation state')
        if error is not None and (not isinstance(error,str) or len(error)>1000):
            raise ValueError('Invalid operation error')
        content=encode(result) if result is not None else None
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            previous=db.execute("SELECT result FROM operations WHERE id=? AND state='running'",(oid,)).fetchone()
            if previous is None:raise ValueError('Operation missing or already terminal')
            if state=='completed' and db.execute('SELECT 1 FROM operation_cancellations WHERE operation=?',(oid,)).fetchone():
                state='cancelled'
                error='Cancellation requested; in-flight response retained, no automatic retry. Charges may apply.'
            if content is not None:require_capacity(db,max(0,len(content.encode())-len((previous['result'] or '').encode())))
            changed = db.execute('UPDATE operations SET state=?,result=?,error=?,updated=? WHERE id=? AND state=?',
                                 (state,content,error,now(),oid,'running'))
            if not changed.rowcount:
                raise ValueError('Operation missing or already terminal')

    def fail_preserving_checkpoint(self, oid, error):
        """Terminate without replacing evidence when a new trace cannot be stored."""
        if not isinstance(error,str) or not 1<=len(error)<=1000:
            raise ValueError('Invalid operation error')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            changed=db.execute("UPDATE operations SET state='failed',error=?,updated=? WHERE id=? AND state='running'",
                               (error,now(),oid))
            if not changed.rowcount:raise ValueError('Operation missing or already terminal')

    def recover_interrupted(self):
        """Call only after acquiring exclusive server ownership, never on reads."""
        with self.connect() as db:
            return db.execute("UPDATE operations SET state='interrupted',error='Server stopped before completion; inspect before retry',updated=? WHERE state='running'", (now(),)).rowcount
