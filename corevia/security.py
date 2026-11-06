"""Server-side sessions and persistent login throttling, outside personnel backups."""
from contextlib import contextmanager
import hashlib
import secrets
import sqlite3
import time

class SecurityStore:
    def __init__(self,path,idle_seconds,absolute_seconds):
        self.path=path;self.idle=idle_seconds;self.absolute=absolute_seconds
        with self.connection() as db:
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, uid INTEGER NOT NULL, fingerprint TEXT NOT NULL, created REAL NOT NULL, seen REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS sessions_uid ON sessions(uid);
            CREATE TABLE IF NOT EXISTS failures(bucket TEXT NOT NULL, at REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS failures_bucket_at ON failures(bucket,at);
            ''')
        path.chmod(0o600)

    @contextmanager
    def connection(self):
        db=sqlite3.connect(self.path,timeout=15)
        db.row_factory=sqlite3.Row
        try:
            yield db;db.commit()
        except Exception:
            db.rollback();raise
        finally:db.close()

    @staticmethod
    def digest(value):return hashlib.sha256(value.encode()).hexdigest()

    def issue(self,user):
        token=secrets.token_urlsafe(32);now=time.time()
        with self.connection() as db:
            db.execute('DELETE FROM sessions WHERE created<? OR seen<?',(now-self.absolute,now-self.idle))
            db.execute('INSERT INTO sessions VALUES(?,?,?,?,?)',(self.digest(token),user['id'],self.digest(user['password']),now,now))
        return token

    def valid(self,token,user,touch=True):
        if not token or not user or not user['active']:return False
        digest=self.digest(token);now=time.time()
        with self.connection() as db:
            row=db.execute('SELECT * FROM sessions WHERE token=?',(digest,)).fetchone()
            if not row:return False
            if row['uid']!=user['id'] or row['fingerprint']!=self.digest(user['password']) or now-row['created']>self.absolute or now-row['seen']>self.idle:
                db.execute('DELETE FROM sessions WHERE token=?',(digest,));return False
            if touch and now-row['seen']>=30:db.execute('UPDATE sessions SET seen=? WHERE token=?',(now,digest))
        return True

    def revoke(self,token=None,uid=None):
        with self.connection() as db:
            if token:db.execute('DELETE FROM sessions WHERE token=?',(self.digest(token),))
            elif uid is not None:db.execute('DELETE FROM sessions WHERE uid=?',(uid,))
            else:db.execute('DELETE FROM sessions')

    def bucket(self,ip,username):return self.digest(str(ip)+'|'+str(username).strip().casefold())

    def blocked(self,bucket):
        with self.connection() as db:
            db.execute('DELETE FROM failures WHERE at<?',(time.time()-300,))
            return db.execute('SELECT count(*) FROM failures WHERE bucket=?',(bucket,)).fetchone()[0]>=10

    def failure(self,bucket):
        with self.connection() as db:db.execute('INSERT INTO failures VALUES(?,?)',(bucket,time.time()))

    def clear_failures(self,bucket):
        with self.connection() as db:db.execute('DELETE FROM failures WHERE bucket=?',(bucket,))
