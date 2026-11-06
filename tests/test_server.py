import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from app import create_app, SCHEMA
from corevia.config import load_settings
from corevia.storage import backup_database, process_lock
from manage import cli
from click.testing import CliRunner
from werkzeug.security import generate_password_hash

PASSWORD='clave-ficticia-segura-1234'
HOST='corevia.test'
HEADERS={'X-Forwarded-Proto':'https','X-Forwarded-For':'10.1.2.3'}
BASE='https://'+HOST

class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.data=self.root/'central'
        self.config=self.root/'production.toml'
        self.config.write_text(f'''environment="production"
data_dir="{self.data.as_posix()}"
backup_dir="{(self.root/'backups').as_posix()}"
log_dir="{(self.root/'logs').as_posix()}"
allowed_hosts=["{HOST}"]
allowed_networks=["10.1.0.0/16"]
''')
        self.env=patch.dict(os.environ,{'COREVIA_CONFIG':str(self.config),'COREVIA_ENV':'production','RRHH_DATA':str(self.data),'RRHH_HOST':'127.0.0.1'});self.env.start()
        self.app=create_app()
        result=self.app.test_cli_runner().invoke(args=['create-admin','rrhh'],input=PASSWORD+'\n'+PASSWORD+'\n')
        self.assertEqual(result.exit_code,0,result.output)
    def tearDown(self):self.env.stop();self.tmp.cleanup()
    def get(self,c,path,headers=None,**kw):return c.get(path,base_url=BASE,headers=headers or HEADERS,**kw)
    def client(self,username='rrhh',password=PASSWORD):
        c=self.app.test_client();r=self.get(c,'/')
        token=re.search(r'name="csrf" content="([^"]+)"',r.text).group(1)
        self.assertEqual(self.post(c,'login',dict(username=username,password=password),token=token,revision=False).status_code,200)
        return c,token
    def post(self,c,path,data,token,revision=True,headers=None):
        h={**HEADERS,'X-CSRF-Token':token}
        if revision is True:
            r=self.get(c,'/api/data');self.assertEqual(r.status_code,200,r.json);h['If-Match']=str(r.json['revision'])
        elif revision is not False:h['If-Match']=str(revision)
        if headers:h.update(headers)
        return c.post('/api/'+path,json=data,base_url=BASE,headers=h)
    def employee(self,code='T1',first='Persona'):
        return dict(code=code,first=first,last='Ficticia',sector='Pruebas',position='Analista',hired='2020-01-01')
    def test_production_rejects_http_wrong_hosts_networks_and_direct_access(self):
        c=self.app.test_client()
        self.assertEqual(c.get('/',base_url=BASE,headers={**HEADERS,'X-Forwarded-Proto':'http'}).status_code,403)
        self.assertEqual(c.get('/',base_url='https://no-autorizado.test',headers=HEADERS).status_code,400)
        self.assertEqual(c.get('/',base_url=BASE,headers={**HEADERS,'X-Forwarded-For':'203.0.113.1'}).status_code,403)
        self.assertEqual(c.get('/',base_url=BASE,headers=HEADERS,environ_overrides={'REMOTE_ADDR':'10.1.2.9'}).status_code,403)
        self.assertEqual(c.get('/',base_url='https://localhost',headers=HEADERS).status_code,400)
        self.assertEqual(c.get('/healthz',base_url='http://127.0.0.1').json,dict(status='ok',application='Corevia'))
    def test_secure_cookies_headers_and_web_bootstrap_disabled(self):
        c=self.app.test_client();r=self.get(c,'/')
        self.assertIn('Secure',r.headers['Set-Cookie']);self.assertIn('HttpOnly',r.headers['Set-Cookie']);self.assertIn('SameSite=Strict',r.headers['Set-Cookie'])
        self.assertIn('Strict-Transport-Security',r.headers)
        token=re.search(r'name="csrf" content="([^"]+)"',r.text).group(1)
        self.assertEqual(self.post(c,'setup',dict(username='other',password=PASSWORD),token,False).status_code,403)
    def test_persistent_sessions_logout_replay_and_idle_expiry(self):
        c,token=self.client();cookie=c.get_cookie('corevia_session',domain=HOST).value
        other=create_app().test_client();other.set_cookie('corevia_session',cookie,domain=HOST)
        self.assertEqual(self.get(other,'/api/data').status_code,200)
        self.post(c,'logout',{},token,False)
        other.set_cookie('corevia_session',cookie,domain=HOST);self.assertEqual(self.get(other,'/api/data').status_code,401)
        c,token=self.client()
        with sqlite3.connect(self.data/'security.sqlite') as db:db.execute('UPDATE sessions SET seen=?',(time.time()-1900,));db.commit()
        self.assertEqual(self.get(c,'/api/data').status_code,401)
        c,token=self.client()
        with sqlite3.connect(self.data/'security.sqlite') as db:db.execute('UPDATE sessions SET created=?',(time.time()-30000,));db.commit()
        self.assertEqual(self.get(c,'/api/data').status_code,401)
    def test_roles_password_change_deactivation_and_last_admin(self):
        c,t=self.client()
        self.assertEqual(self.post(c,'users',dict(username='gerencia',password=PASSWORD,role='lectura'),t).status_code,200)
        read,rt=self.client('gerencia')
        self.assertEqual(self.post(read,'employees',self.employee(),rt).status_code,403)
        self.assertEqual(self.get(read,'/api/backup').status_code,403)
        self.assertEqual(self.post(read,'users/manage',dict(id=1,role='lectura',active=False),rt).status_code,403)
        users=self.get(c,'/api/users').json;admin=next(u for u in users if u['role']=='admin');manager=next(u for u in users if u['role']=='lectura')
        self.assertEqual(self.post(c,'users/manage',dict(id=admin['id'],role='lectura',active=False),t).status_code,400)
        self.assertEqual(self.post(c,'users/manage',dict(id=manager['id'],role='lectura',active=False),t).status_code,200)
        self.assertEqual(self.get(read,'/api/data').status_code,401)
        self.assertEqual(self.post(c,'password',dict(current=PASSWORD,password='nueva-clave-ficticia-5678'),t,False).status_code,200)
        self.assertEqual(self.get(c,'/api/data').status_code,401)
        c,t=self.client(password='nueva-clave-ficticia-5678')
        with sqlite3.connect(self.data/'rrhh.sqlite') as db:stored=db.execute('SELECT password FROM users WHERE username=?',('rrhh',)).fetchone()[0]
        self.assertTrue(stored.startswith('scrypt:'));self.assertNotEqual(stored,PASSWORD)
    def test_login_throttle_survives_app_restart(self):
        c=self.app.test_client();r=self.get(c,'/');t=re.search(r'name="csrf" content="([^"]+)"',r.text).group(1)
        for _ in range(10):self.assertEqual(self.post(c,'login',dict(username='rrhh',password='incorrecta'),t,False).status_code,401)
        self.app=create_app();c=self.app.test_client();r=self.get(c,'/');t=re.search(r'name="csrf" content="([^"]+)"',r.text).group(1)
        self.assertEqual(self.post(c,'login',dict(username='rrhh',password=PASSWORD),t,False).status_code,429)
    def test_missing_revision_and_concurrent_stale_writes(self):
        c1,t1=self.client();c2,t2=self.client();rev=self.get(c1,'/api/data').json['revision']
        self.assertEqual(self.post(c1,'employees',self.employee(),t1,False).status_code,428)
        barrier=threading.Barrier(2)
        def save(c,t,code):
            barrier.wait();return self.post(c,'employees',self.employee(code),t,rev).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(save,c1,t1,'A');b=pool.submit(save,c2,t2,'B');statuses=[a.result(),b.result()]
        self.assertEqual(sorted(statuses),[200,409]);self.assertEqual(len(self.get(c2,'/api/data').json['employees']),1)
        self.assertEqual(self.post(c2,'employees',self.employee('C'),t2).status_code,200)
        self.assertEqual(len(self.get(c1,'/api/data').json['employees']),2)
    def test_waiting_write_revalidates_revoked_role_after_lock(self):
        admin,token=self.client()
        self.post(admin,'users',dict(username='second-admin',password=PASSWORD,role='admin'),token)
        target,t2=self.client('second-admin')
        users=self.get(admin,'/api/users').json;uid=next(u['id'] for u in users if u['username']=='second-admin')
        rev=self.get(admin,'/api/data').json['revision'];entered=threading.Event();resume=threading.Event()
        store=self.app.extensions['corevia_security'];original=store.valid;blocked=[False]
        def delayed(sid,user,touch=True):
            value=original(sid,user,touch)
            if user and user['id']==uid and not blocked[0]:
                blocked[0]=True;entered.set();resume.wait(5)
            return value
        with patch.object(store,'valid',side_effect=delayed),ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(self.post,target,'employees',self.employee('RACE'),t2,rev+1)
            self.assertTrue(entered.wait(5))
            try:self.assertEqual(self.post(admin,'users/manage',dict(id=uid,role='admin',active=False),token).status_code,200)
            finally:resume.set()
            self.assertEqual(future.result().status_code,401)
        self.assertEqual(self.get(admin,'/api/data').json['employees'],[])

    def test_backup_wal_manifest_migration_refuses_overwrite_and_restore_lock(self):
        c,t=self.client();self.post(c,'employees',self.employee(),t)
        copy=backup_database(self.data/'rrhh.sqlite',self.root/'copies')
        manifest=json.loads(copy.with_suffix('.json').read_text());self.assertEqual(manifest['sha256'],hashlib.sha256(copy.read_bytes()).hexdigest())
        with sqlite3.connect(copy) as db:self.assertEqual(db.execute('PRAGMA journal_mode').fetchone()[0],'delete')
        runner=CliRunner()
        with process_lock(self.data):
            blocked=runner.invoke(cli,['restore',str(copy),'--confirm','RESTAURAR']);self.assertNotEqual(blocked.exit_code,0);self.assertIn('ejecución',blocked.output)
        target=self.root/'new-central'
        original=hashlib.sha256(copy.read_bytes()).hexdigest()
        with patch.dict(os.environ,{'RRHH_DATA':str(target)}):
            result=runner.invoke(cli,['migrate',str(copy)]);self.assertEqual(result.exit_code,0,result.output)
            again=runner.invoke(cli,['migrate',str(copy)]);self.assertNotEqual(again.exit_code,0)
            self.assertEqual(hashlib.sha256(copy.read_bytes()).hexdigest(),original)
            self.assertEqual(runner.invoke(cli,['check']).exit_code,0)
        self.post(c,'employees',self.employee('EXTRA'),t)
        restored=runner.invoke(cli,['restore',str(copy),'--confirm','RESTAURAR']);self.assertEqual(restored.exit_code,0,restored.output)
        self.assertEqual(self.get(c,'/api/data').status_code,401)
        c,t=self.client();self.assertEqual(len(self.get(c,'/api/data').json['employees']),1)
        self.assertTrue(list((self.root/'backups').glob('antes-restauracion-*.sqlite')))
    def test_production_disables_online_restore_demo_and_csrf(self):
        c,t=self.client()
        self.assertEqual(self.post(c,'demo',{},t).status_code,403)
        self.assertEqual(self.post(c,'restore',{},t,False).status_code,403)
        self.assertEqual(c.post('/api/employees',base_url=BASE,headers=HEADERS,json=self.employee()).status_code,400)
    def test_error_logs_and_responses_do_not_contain_sensitive_exception_text(self):
        @self.app.get('/simulate-error')
        def simulate():raise RuntimeError('CONTRASENA-Y-DATO-PERSONAL-NO-REGISTRAR')
        c=self.app.test_client();r=self.get(c,'/simulate-error');self.assertEqual(r.status_code,500)
        text=(self.root/'logs'/'corevia.log').read_text()
        self.assertIn('incident=',text);self.assertIn('RuntimeError',text)
        self.assertNotIn('CONTRASENA',text+r.text)
    def test_background_refresh_does_not_extend_idle_session(self):
        c,t=self.client()
        previous=time.time()-120
        with sqlite3.connect(self.data/'security.sqlite') as db:db.execute('UPDATE sessions SET seen=?',(previous,));db.commit()
        r=self.get(c,'/api/data',headers={**HEADERS,'X-Corevia-Background':'1'});self.assertEqual(r.status_code,200)
        with sqlite3.connect(self.data/'security.sqlite') as db:self.assertEqual(db.execute('SELECT seen FROM sessions').fetchone()[0],previous)
        self.assertEqual(self.get(c,'/api/data').status_code,200)
        with sqlite3.connect(self.data/'security.sqlite') as db:self.assertGreater(db.execute('SELECT seen FROM sessions').fetchone()[0],previous)

    def test_production_configuration_fails_closed(self):
        with patch.dict(os.environ,{'COREVIA_ALLOWED_HOSTS':'COREVIA.TEST'}):self.assertEqual(load_settings().allowed_hosts,('corevia.test',))
        for env in [{'RRHH_HOST':'0.0.0.0'},{'RRHH_DATA':'data'},{'COREVIA_ALLOWED_HOSTS':'*'},{'COREVIA_ALLOWED_NETWORKS':'0.0.0.0/0'}]:
            with patch.dict(os.environ,env):
                with self.assertRaises(ValueError):load_settings()
    def test_legacy_migration_preserves_hashes_and_creates_backup(self):
        legacy=self.root/'legacy';legacy.mkdir(mode=0o700)
        digest=generate_password_hash(PASSWORD)
        with sqlite3.connect(legacy/'rrhh.sqlite') as db:
            db.executescript(SCHEMA)
            db.execute("INSERT INTO users(username,password,role) VALUES(?,?,'admin')",('legacy',digest));db.commit()
        with patch.dict(os.environ,{'RRHH_DATA':str(legacy)}):
            create_app()
            with sqlite3.connect(legacy/'rrhh.sqlite') as db:
                row=db.execute('SELECT password,active FROM users').fetchone();self.assertEqual(row,(digest,1))
            self.assertTrue(list((self.root/'backups').glob('antes-migracion-*.sqlite')))

if __name__=='__main__':unittest.main()
