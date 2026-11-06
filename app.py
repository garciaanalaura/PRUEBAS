from __future__ import annotations
import calendar, io, os, secrets, sqlite3
import click
import ipaddress, logging, threading, traceback, uuid, tempfile
from urllib.parse import urlsplit
from logging.handlers import RotatingFileHandler
from werkzeug.middleware.proxy_fix import ProxyFix
from corevia.config import load_settings
from corevia.storage import backup_database, readonly
from corevia.security import SecurityStore
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path
from contextlib import closing
from flask import Flask, abort, g, jsonify, render_template, request, session, send_file, has_request_context
from werkzeug.security import generate_password_hash, check_password_hash
from openpyxl import Workbook, load_workbook

TYPES = ['Vacaciones','Enfermedad','Estudio','Maternidad','Paternidad','Matrimonio','Fallecimiento de familiar','Trámites personales','Otras']
OPENING_SCHEMA = '''CREATE TABLE IF NOT EXISTS opening_balances(employee INTEGER NOT NULL REFERENCES employees(id), year INTEGER NOT NULL CHECK(year BETWEEN 1900 AND 2200), cutoff TEXT NOT NULL, remaining REAL NOT NULL CHECK(remaining >= 0), reason TEXT NOT NULL, PRIMARY KEY(employee,year));'''

ACCRUAL_SCHEMA = """CREATE TABLE IF NOT EXISTS accruals(employee INTEGER NOT NULL REFERENCES employees(id), year INTEGER NOT NULL, asof TEXT NOT NULL, worked_days INTEGER, acquired REAL, reason TEXT NOT NULL, PRIMARY KEY(employee,year));"""

STATES = ['Solicitadas','Aprobadas','Rechazadas','Canceladas','Disfrutadas']
SCHEMA = '''
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','lectura')));
CREATE TABLE IF NOT EXISTS employees(id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, first TEXT NOT NULL, last TEXT NOT NULL, sector TEXT NOT NULL, position TEXT NOT NULL, hired TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, notes TEXT NOT NULL DEFAULT '', demo INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS balances(employee INTEGER REFERENCES employees(id), year INTEGER NOT NULL, assigned REAL NOT NULL, adjustment REAL NOT NULL DEFAULT 0, reason TEXT NOT NULL DEFAULT '', PRIMARY KEY(employee,year));
CREATE TABLE IF NOT EXISTS absences(id INTEGER PRIMARY KEY, employee INTEGER NOT NULL REFERENCES employees(id), type TEXT NOT NULL, year INTEGER NOT NULL, start TEXT NOT NULL, end TEXT NOT NULL, state TEXT NOT NULL, requested TEXT NOT NULL, approved TEXT NOT NULL DEFAULT '', approver TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS types(name TEXT PRIMARY KEY, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, at TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL);
'''

META_SCHEMA = """CREATE TABLE IF NOT EXISTS app_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
INSERT OR IGNORE INTO app_meta VALUES('revision','0');
INSERT OR IGNORE INTO app_meta VALUES('schema_version','2');
CREATE INDEX IF NOT EXISTS absences_employee_year ON absences(employee,year);
CREATE INDEX IF NOT EXISTS absences_dates ON absences(start,end);
"""

def migrate_schema(connection):
    if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='app_meta'").fetchone():
        previous=connection.execute("SELECT value FROM app_meta WHERE key='schema_version'").fetchone()
        if previous and int(previous[0])>2:raise ValueError('Esta base requiere una versión más nueva de Corevia.')
    connection.executescript(SCHEMA+OPENING_SCHEMA+ACCRUAL_SCHEMA+META_SCHEMA)
    if 'active' not in {r[1] for r in connection.execute('PRAGMA table_info(users)')}:
        connection.execute('ALTER TABLE users ADD COLUMN active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))')
    version=int(connection.execute("SELECT value FROM app_meta WHERE key='schema_version'").fetchone()[0])
    if version>2:raise ValueError('Esta base requiere una versión más nueva de Corevia.')
    connection.execute("UPDATE app_meta SET value='2' WHERE key='schema_version'")
    connection.commit()


def prepare_candidate(candidate):
    if candidate.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('La copia está dañada.')
    objects=candidate.execute("SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall()
    allowed={'users','employees','balances','absences','types','audit','opening_balances','accruals','app_meta'}
    if any(r[0] in ('trigger','view') or (r[0]=='table' and (r[1] not in allowed or 'VIRTUAL' in (r[2] or '').upper())) for r in objects):
        raise ValueError('La copia contiene objetos incompatibles.')
    required={'users','employees','balances','absences','types','audit'}
    if not required.issubset({r[1] for r in objects if r[0]=='table'}):raise ValueError('Faltan tablas de Corevia en la copia.')
    migrate_schema(candidate)
    with closing(sqlite3.connect(':memory:')) as expected:
        migrate_schema(expected)
        for table in allowed:
            if [tuple(r[1:3]) for r in candidate.execute(f'PRAGMA table_info({table})')]!=[tuple(r[1:3]) for r in expected.execute(f'PRAGMA table_info({table})')]:
                raise ValueError('La estructura de la copia no es compatible.')
    if candidate.execute('PRAGMA foreign_key_check').fetchone():raise ValueError('La copia contiene referencias inválidas.')
    return candidate

def suggested(hired, year):
    start = date.fromisoformat(hired); cutoff = date(year,12,31)
    if start > cutoff: return None
    # Employment duration alone does not establish the days actually worked (LCT arts. 151/153).
    if start > date(year,1,1): return None
    years = cutoff.year-start.year-((cutoff.month,cutoff.day)<(start.month,start.day))
    return 14 if years <= 5 else 21 if years <= 10 else 28 if years <= 20 else 35

def weekdays(start,end):
    if end<start:return 0
    weeks,extra=divmod((end-start).days+1,7)
    return weeks*5+sum((start.weekday()+i)%7<5 for i in range(extra))

def accrual_estimate(hired,year,asof,worked_days=None):
    """Indicative Mon–Fri model, not an attendance record or a legal determination."""
    hired=date.fromisoformat(hired);asof=date.fromisoformat(asof)
    start=max(hired,date(year,1,1));end=min(asof,date(year,12,31))
    estimate=weekdays(start,end)
    worked=estimate if worked_days is None else worked_days
    annual_days=weekdays(date(year,1,1),date(year,12,31))
    threshold=(annual_days+1)//2
    cutoff=date(year,12,31)
    seniority=year-hired.year-((12,31)<(hired.month,hired.day))
    full=0 if hired>cutoff else 14 if seniority<=5 else 21 if seniority<=10 else 28 if seniority<=20 else 35
    earned=(full if worked>=threshold else worked//20) if end>=start else 0
    projected_work=worked+weekdays(max(start,end+timedelta(days=1)),cutoff)
    projected=full if projected_work>=threshold else projected_work//20
    return dict(estimated_acquired=earned,projected_closing=projected,worked_days=worked,estimated_workdays=estimate,full_entitlement=full,half_year_threshold=threshold,asof=end.isoformat(),source='RRHH' if worked_days is not None else 'Estimación lunes a viernes, sin feriados ni asistencia')

def days(start,end):
    a,b=date.fromisoformat(start),date.fromisoformat(end)
    if b<a: raise ValueError('La fecha final debe ser igual o posterior al inicio.')
    return (b-a).days+1

def create_app(data_dir=None):
    app=Flask(__name__)
    settings=load_settings(data_dir)
    root=settings.data_dir;root.mkdir(mode=0o700,parents=True,exist_ok=True)
    if settings.production and os.name!='nt' and root.stat().st_mode & 0o007:raise ValueError('La carpeta de datos no debe permitir acceso a otros usuarios del sistema. Revisá sus permisos.')
    key=root/'session.key'
    if not key.exists():
        try:
            with key.open('x',encoding='utf-8') as target:target.write(secrets.token_hex(32))
            key.chmod(0o600)
        except FileExistsError:pass
    if len(key.read_text().strip())<32:raise ValueError('La clave de sesión no es válida. No sobrescribas una clave existente sin investigar.')
    app.config.update(SECRET_KEY=key.read_text(),DATABASE=str(root/'rrhh.sqlite'),MAX_CONTENT_LENGTH=10*1024*1024,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SECURE=settings.secure_cookie,SESSION_COOKIE_SAMESITE='Strict',SESSION_COOKIE_NAME='corevia_session',SESSION_REFRESH_EACH_REQUEST=False,PERMANENT_SESSION_LIFETIME=timedelta(seconds=settings.absolute_seconds),TRUSTED_HOSTS=list(settings.allowed_hosts)+(['localhost','127.0.0.1','::1'] if settings.production else []))
    app.extensions['corevia_settings']=settings
    store=SecurityStore(root/'security.sqlite',settings.idle_seconds,settings.absolute_seconds)
    app.extensions['corevia_security']=store
    write_lock=threading.RLock()
    if settings.production:
        app.wsgi_app=ProxyFix(app.wsgi_app,x_for=1,x_proto=1)
    settings.log_dir.mkdir(mode=0o700,parents=True,exist_ok=True)
    logger=logging.getLogger('corevia.'+uuid.uuid4().hex)
    handler=RotatingFileHandler(settings.log_dir/'corevia.log',maxBytes=2*1024*1024,backupCount=5,encoding='utf-8',delay=True)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger.addHandler(handler);logger.setLevel(logging.INFO);logger.propagate=False
    app.extensions['corevia_logger']=logger
    def db():
        if 'db' not in g:
            g.db=sqlite3.connect(app.config['DATABASE'],timeout=15); g.db.row_factory=sqlite3.Row; g.db.execute('PRAGMA foreign_keys=ON');g.db.execute('PRAGMA busy_timeout=15000');g.db.execute('PRAGMA trusted_schema=OFF')
        return g.db
    @app.teardown_appcontext
    def close(_):
        if 'db' in g: g.db.close()
        if g.pop('write_locked',False):write_lock.release()
        handler.close()
    with app.app_context():
        path=Path(app.config['DATABASE'])
        if path.exists():
            with readonly(path) as previous:
                tables={r[0] for r in previous.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                cols={r[1] for r in previous.execute('PRAGMA table_info(users)')}
                if tables and ('active' not in cols or not {'app_meta','opening_balances','accruals'}.issubset(tables)):
                    backup_database(path,settings.backup_dir,'antes-migracion')
        migrate_schema(db())
        db().execute('PRAGMA journal_mode=WAL');db().execute('PRAGMA synchronous=FULL')
        if not db().execute('SELECT 1 FROM types').fetchone():db().executemany('INSERT INTO types(name) VALUES(?)',[(t,) for t in TYPES])
        db().commit()
        for suffix in ('','-wal','-shm'):
            protected=Path(str(path)+suffix)
            if protected.exists():protected.chmod(0o600)
    def begin_write():
        if not db().in_transaction:db().execute('BEGIN IMMEDIATE')
    def commit_changes():
        db().execute("UPDATE app_meta SET value=CAST(value AS INTEGER)+1 WHERE key='revision'")
        db().commit()
    def revision():return int(db().execute("SELECT value FROM app_meta WHERE key='revision'").fetchone()[0])
    def current_user():
        if 'current_user' in g:return g.current_user
        u=db().execute('SELECT * FROM users WHERE id=?',(session.get('uid'),)).fetchone()
        if not store.valid(session.get('sid'),u,touch=request.headers.get('X-Corevia-Background')!='1'):
            for name in ('uid','username','role','sid'):session.pop(name,None)
            u=None
        g.current_user=u
        return u
    def audit(action,detail=''):
        db().execute('INSERT INTO audit(at,actor,action,detail) VALUES(?,?,?,?)',(datetime.now().isoformat(timespec='seconds'),session.get('username','Inicialización') if has_request_context() else 'Sistemas (CLI)',action,str(detail)))
    def auth(admin=False):
        def deco(fn):
            @wraps(fn)
            def wrapped(*a,**kw):
                u=current_user()
                if not u: abort(401,description='La sesión venció o fue revocada. Volvé a ingresar.')
                if admin and u['role']!='admin': abort(403)
                return fn(*a,**kw)
            return wrapped
        return deco
    protected_writes={'save_employee','save_balance','save_accrual','save_opening','save_absence','save_type','user','manage_user','import_excel','demo'}
    @app.before_request
    def csrf():
        if settings.production:
            original=request.environ.get('werkzeug.proxy_fix.orig',{}).get('REMOTE_ADDR',request.remote_addr)
            try:local_peer=ipaddress.ip_address(original).is_loopback
            except (ValueError,TypeError):local_peer=False
            if not local_peer:abort(403,description='Acceso directo al servicio no permitido.')
            if request.endpoint=='health':return
            hostname=urlsplit('http://'+request.host).hostname
            if hostname not in settings.allowed_hosts:abort(400,description='Nombre de servidor no autorizado.')
            if not request.is_secure:abort(403,description='Corevia requiere HTTPS en producción.')
            try:client=ipaddress.ip_address(request.remote_addr)
            except (ValueError,TypeError):abort(403)
            if not any(client in network for network in settings.allowed_networks):abort(403,description='Red no autorizada.')
        if request.endpoint=='health':return
        if 'csrf' not in session:session['csrf']=secrets.token_hex(24)
        if request.method in ('POST','PUT','DELETE') and request.headers.get('X-CSRF-Token')!=session['csrf']:abort(400,description='Sesión vencida. Recargá la página.')
        if request.method=='POST' and request.endpoint=='restore' and not settings.production:
            if not write_lock.acquire(timeout=15):abort(503)
            g.write_locked=True;g.pop('current_user',None)
        if request.method=='POST' and request.endpoint=='password_change':
            if not write_lock.acquire(timeout=15):abort(503)
            g.write_locked=True;begin_write();g.pop('current_user',None)
        if request.method=='POST' and request.endpoint in protected_writes:
            if not current_user():abort(401,description='Volvé a ingresar.')
            if not write_lock.acquire(timeout=15):abort(503,description='Hay otra operación en curso. Intentá nuevamente.')
            g.write_locked=True;begin_write();g.pop('current_user',None)
            if not current_user():abort(401,description='La sesión fue revocada. Volvé a ingresar.')
            expected=request.headers.get('If-Match')
            if settings.production and expected is None:abort(428,description='Actualizá la página antes de guardar.')
            if expected is not None and expected!=str(revision()):abort(409,description='Otra persona modificó la información. Cerrá el formulario y actualizá la página para revisar los datos antes de guardar nuevamente.')
    @app.after_request
    def headers(r):
        r.headers['X-Content-Type-Options']='nosniff';r.headers['X-Frame-Options']='DENY';r.headers['Cache-Control']='no-store'
        r.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        if settings.production and request.is_secure:r.headers['Strict-Transport-Security']='max-age=31536000'
        if 'db' in g and r.status_code<400:r.headers['X-Corevia-Revision']=str(revision())
        return r
    @app.errorhandler(ValueError)
    def invalid(e): return jsonify(error=str(e)),400
    @app.errorhandler(sqlite3.IntegrityError)
    def conflict(e): return jsonify(error='El identificador o usuario ya existe, o el registro tiene referencias.'),400
    from werkzeug.exceptions import HTTPException
    @app.errorhandler(HTTPException)
    def http_error(e): return jsonify(error=e.description),e.code
    def report_error(e):
        incident=uuid.uuid4().hex[:12]
        frames=';'.join(f'{Path(frame.filename).name}:{frame.lineno}:{frame.name}' for frame in traceback.extract_tb(e.__traceback__))
        logger.error('incident=%s endpoint=%s error_type=%s frames=%s',incident,request.endpoint,type(e).__name__,frames)
        return jsonify(error=f'No se pudo completar la operación. Informá a Sistemas la referencia {incident}.'),500
    @app.errorhandler(sqlite3.OperationalError)
    def storage_error(e):
        if 'locked' in str(e).lower() or 'busy' in str(e).lower():return jsonify(error='La base está ocupada. Intentá nuevamente.'),503
        return report_error(e)
    app.register_error_handler(Exception,report_error)
    @app.get('/healthz')
    def health():
        db().execute('SELECT 1').fetchone()
        return jsonify(status='ok',application='Corevia')
    @app.get('/')
    def index(): return render_template('index.html',csrf=session['csrf'])
    @app.get('/api/session')
    def who():
        u=current_user();empty=not db().execute('SELECT 1 FROM users').fetchone()
        return jsonify(user=u['username'] if u else None,role=u['role'] if u else None,production=settings.production,setup=empty and not settings.production,initialization_required=empty and settings.production,refresh_seconds=settings.refresh_seconds)
    @app.post('/api/setup')
    def setup():
        if settings.production:abort(403,description='Sistemas debe crear el primer administrador desde la consola del servidor.')
        # Serialize first-user creation to prevent two simultaneous administrators.
        begin_write()
        if db().execute('SELECT 1 FROM users').fetchone(): abort(403)
        p=request.get_json(); validate_password(p['password'])
        username=required(p,'username')
        db().execute('INSERT INTO users(username,password,role) VALUES(?,?,?)',(username,generate_password_hash(p['password']),'admin'));audit('Crear administrador');commit_changes()
        return jsonify(ok=True)
    def establish_session(u):
        store.revoke(token=session.get('sid')) if session.get('sid') else None
        token=session.get('csrf') or secrets.token_hex(24)
        session.clear();session.update(csrf=token,uid=u['id'],username=u['username'],role=u['role'],sid=store.issue(u));session.permanent=True
    @app.post('/api/login')
    def login():
        p=request.get_json();username=str(p.get('username','')).strip()
        bucket=store.bucket(request.remote_addr,username)
        if store.blocked(bucket):abort(429,description='Demasiados intentos. Esperá cinco minutos.')
        u=db().execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
        if not u or not check_password_hash(u['password'],p.get('password','')) or not u['active']:
            store.failure(bucket);abort(401,description='Usuario o contraseña incorrectos.')
        establish_session(u);store.clear_failures(bucket)
        return jsonify(ok=True)
    @app.post('/api/logout')
    def logout():
        if session.get('sid'):store.revoke(token=session['sid'])
        session.clear();return jsonify(ok=True)
    def chargeable(start,end,cutoff=None):
        """Snapshot is the balance at the close of cutoff; only subsequent days consume it."""
        if not cutoff: return days(start,end)
        return max(0,(date.fromisoformat(end)-max(date.fromisoformat(start),date.fromisoformat(cutoff)+timedelta(days=1))).days+1)

    def balance(e,year):
        row=db().execute('SELECT * FROM balances WHERE employee=? AND year=?',(e['id'],year)).fetchone()
        opening=db().execute('SELECT * FROM opening_balances WHERE employee=? AND year=?',(e['id'],year)).fetchone()
        cutoff=opening['cutoff'] if opening else None
        suggestion=suggested(e['hired'],year); assigned=row['assigned'] if row else (suggestion or 0); adjustment=row['adjustment'] if row else 0
        accrual=db().execute('SELECT * FROM accruals WHERE employee=? AND year=?',(e['id'],year)).fetchone()
        asof=accrual['asof'] if accrual else date.today().isoformat()
        estimate=accrual_estimate(e['hired'],year,asof,accrual['worked_days'] if accrual else None)
        estimate.update(acquired=accrual['acquired'] if accrual and accrual['acquired'] is not None else estimate['estimated_acquired'],manual=bool(accrual and accrual['acquired'] is not None),record=dict(accrual) if accrual else None,assigned_manual=row is not None)
        used=reserved=deducted_used=included_used=0
        for a in db().execute("SELECT * FROM absences WHERE employee=? AND year=? AND type='Vacaciones'",(e['id'],year)):
            n=days(a['start'],a['end']);charged=chargeable(a['start'],a['end'],cutoff)
            if a['state']=='Disfrutadas' or (a['state']=='Aprobadas' and a['end']<date.today().isoformat()):
                used+=n;deducted_used+=charged;included_used+=n-charged
            elif a['state']=='Aprobadas': reserved+=charged
        base=opening['remaining'] if opening else assigned+adjustment
        return dict(accrual=estimate,assigned=assigned,adjustment=adjustment,reason=row['reason'] if row else '',used=used,reserved=reserved,available=base-deducted_used-reserved,suggested=suggestion,needs_review=suggestion is None and row is None and opening is None,opening=dict(opening) if opening else None,base=base,deducted_used=deducted_used,included_used=included_used)
    def leave_summary(eid,year):
        start=f'{year}-01-01';end=f'{year}-12-31'
        result=dict(used=0,reserved=0,pending=0,total=0,by_type={})
        for a in db().execute("SELECT * FROM absences WHERE employee=? AND type<>'Vacaciones' AND start<=? AND end>=? AND state IN ('Aprobadas','Disfrutadas','Solicitadas')",(eid,end,start)):
            n=days(max(start,a['start']),min(end,a['end']))
            key='pending' if a['state']=='Solicitadas' else 'used' if a['state']=='Disfrutadas' or a['end']<date.today().isoformat() else 'reserved'
            detail=result['by_type'].setdefault(a['type'],dict(used=0,reserved=0,pending=0,total=0))
            result[key]+=n;detail[key]+=n
            if key!='pending':result['total']+=n;detail['total']+=n
        return result
    @app.get('/api/data')
    @auth()
    def data():
        db().execute('BEGIN')
        data_revision=revision()
        year=int(request.args.get('year',date.today().year))
        if not 1900<=year<=2200:raise ValueError('Período anual inválido.')
        employees=[]
        for e in db().execute('SELECT * FROM employees ORDER BY last,first'):
            item=dict(e);item['balance']=balance(e,year);item['leaves']=leave_summary(e['id'],year);item['seniority']=max(0,(date.today()-date.fromisoformat(e['hired'])).days//365);employees.append(item)
        openings={(o['employee'],o['year']):o['cutoff'] for o in db().execute('SELECT * FROM opening_balances')}
        absences=[]
        for a in db().execute('SELECT * FROM absences ORDER BY start'):
            n=days(a['start'],a['end']);cutoff=openings.get((a['employee'],a['year'])) if a['type']=='Vacaciones' else None
            charged=chargeable(a['start'],a['end'],cutoff) if a['type']=='Vacaciones' else 0
            absences.append(dict(a,days=n,chargeable_days=charged,included_days=n-charged if cutoff else 0,cutoff=cutoff))
        today=date.today(); current=today.replace(day=1); following=(current.replace(day=28)+timedelta(days=4)).replace(day=1); after=(following.replace(day=28)+timedelta(days=4)).replace(day=1)
        def counts(a,b):
            records=[r for r in absences if r['state'] in ('Aprobadas','Disfrutadas') and r['start']<b.isoformat() and r['end']>=a.isoformat()]
            return dict(total=len({r['employee'] for r in records}),vacations=len({r['employee'] for r in records if r['type']=='Vacaciones'}),leaves=len({r['employee'] for r in records if r['type']!='Vacaciones'}))
        this_month=counts(current,following);next_month=counts(following,after)
        return jsonify(revision=data_revision,employees=employees,absences=absences,types=[dict(t) for t in db().execute('SELECT * FROM types ORDER BY name')],stats=dict(active=sum(e['active'] for e in employees),current=this_month['total'],next=next_month['total'],current_detail=this_month,next_detail=next_month),today=today.isoformat())
    def employee_values(p):
        hired=required(p,'hired'); date.fromisoformat(hired)
        if hired>date.today().isoformat(): raise ValueError('La fecha de ingreso no puede ser futura.')
        return (required(p,'code'),required(p,'first'),required(p,'last'),required(p,'sector'),required(p,'position'),hired,int(bool(p.get('active',True))),p.get('notes','')[:2000])
    @app.post('/api/employees')
    @auth(True)
    def save_employee():
        p=request.get_json();v=employee_values(p);eid=p.get('id')
        if eid:
            if not db().execute('SELECT 1 FROM employees WHERE id=?',(eid,)).fetchone():abort(404)
            db().execute('UPDATE employees SET code=?,first=?,last=?,sector=?,position=?,hired=?,active=?,notes=? WHERE id=?',v+(eid,))
        else: eid=db().execute('INSERT INTO employees(code,first,last,sector,position,hired,active,notes) VALUES(?,?,?,?,?,?,?,?)',v).lastrowid
        audit('Guardar empleado',eid);commit_changes();return jsonify(id=eid)
    @app.post('/api/balances')
    @auth(True)
    def save_balance():
        p=request.get_json();assigned=float(p['assigned']);adjustment=float(p.get('adjustment',0));year=int(p['year'])
        import math
        if not math.isfinite(assigned) or not math.isfinite(adjustment) or assigned<0 or not 1900<=year<=2200:raise ValueError('Saldo o período inválido.')
        reason=required(p,'reason')
        db().execute('INSERT INTO balances VALUES(?,?,?,?,?) ON CONFLICT(employee,year) DO UPDATE SET assigned=excluded.assigned,adjustment=excluded.adjustment,reason=excluded.reason',(int(p['employee']),year,assigned,adjustment,reason));audit('Ajustar saldo',f"{p['employee']} / {year}: asignados {assigned}, ajuste {adjustment}, motivo {reason}");commit_changes();return jsonify(ok=True)
    @app.post('/api/accruals')
    @auth(True)
    def save_accrual():
        import math
        p=request.get_json();eid=int(required(p,'employee'));year=int(required(p,'year'));reason=required(p,'reason')
        if not 1900<=year<=2200:raise ValueError('Período anual inválido.')
        asof=required(p,'asof')
        if date.fromisoformat(asof).isoformat()!=asof or asof>date.today().isoformat() or not date(year,1,1)<=date.fromisoformat(asof)<=date(year,12,31):raise ValueError('La fecha de cómputo debe pertenecer al período y no ser futura.')
        def optional_number(name,whole=False):
            raw=p.get(name)
            if raw is None or raw=='':return None
            try:value=float(raw)
            except (TypeError,ValueError):raise ValueError('Los días deben ser numéricos.')
            if isinstance(raw,bool) or not math.isfinite(value) or value<0 or (whole and not value.is_integer()):raise ValueError('Los días deben ser positivos o cero; los trabajados deben ser enteros.')
            return int(value) if whole else value
        worked=optional_number('worked_days',True);acquired=optional_number('acquired');assigned=optional_number('assigned')
        begin_write()
        e=db().execute('SELECT * FROM employees WHERE id=?',(eid,)).fetchone()
        if not e:raise ValueError('El empleado no existe.')
        if asof<e['hired']:raise ValueError('La fecha de cómputo no puede ser anterior al ingreso.')
        if worked is not None and worked>days(max(e['hired'],f'{year}-01-01'),asof):raise ValueError('Los días computables no pueden superar los días corridos transcurridos del período.')
        previous=db().execute('SELECT * FROM accruals WHERE employee=? AND year=?',(eid,year)).fetchone()
        if p.get('reset'):
            db().execute('DELETE FROM accruals WHERE employee=? AND year=?',(eid,year))
        else:
            db().execute('INSERT INTO accruals VALUES(?,?,?,?,?,?) ON CONFLICT(employee,year) DO UPDATE SET asof=excluded.asof,worked_days=excluded.worked_days,acquired=excluded.acquired,reason=excluded.reason',(eid,year,asof,worked,acquired,reason))
        if assigned is not None:
            existing=db().execute('SELECT adjustment FROM balances WHERE employee=? AND year=?',(eid,year)).fetchone()
            adjustment=existing['adjustment'] if existing else 0
            db().execute('INSERT INTO balances VALUES(?,?,?,?,?) ON CONFLICT(employee,year) DO UPDATE SET assigned=excluded.assigned,reason=excluded.reason',(eid,year,assigned,adjustment,reason))
        audit('Editar adquiridos y período',f'{eid}/{year}: anterior {dict(previous) if previous else None}; fecha {asof}; trabajados {worked}; adquiridos {acquired}; asignados {assigned}; reiniciar {bool(p.get("reset"))}; motivo {reason}')
        commit_changes();return jsonify(ok=True)
    @app.post('/api/opening-balances')
    @auth(True)
    def save_opening():
        import math
        p=request.get_json();eid=int(required(p,'employee'));year=int(required(p,'year'));reason=required(p,'reason')
        if not 1900<=year<=2200:raise ValueError('Período anual inválido.')
        begin_write()
        e=db().execute('SELECT * FROM employees WHERE id=?',(eid,)).fetchone()
        if not e:raise ValueError('El empleado no existe.')
        previous=db().execute('SELECT * FROM opening_balances WHERE employee=? AND year=?',(eid,year)).fetchone()
        before=balance(e,year)['available']
        if p.get('clear'):
            if p.get('confirm') is not True:raise ValueError('Confirmá el regreso al cálculo por asignación anual.')
            db().execute('DELETE FROM opening_balances WHERE employee=? AND year=?',(eid,year))
        else:
            cutoff=required(p,'cutoff')
            if date.fromisoformat(cutoff).isoformat()!=cutoff:raise ValueError('La fecha de corte debe usar el formato AAAA-MM-DD.')
            if cutoff>date.today().isoformat() or cutoff<e['hired']:raise ValueError('La fecha de corte debe estar entre el ingreso y hoy.')
            remaining=float(required(p,'remaining') if p.get('remaining') != 0 else '0')
            if not math.isfinite(remaining) or remaining<0:raise ValueError('Los días restantes deben ser un número finito mayor o igual a cero.')
            if p.get('confirm') is not True:raise ValueError('Confirmá que el saldo ya contempla las vacaciones hasta la fecha de corte y no descuenta reservas posteriores.')
            db().execute('INSERT INTO opening_balances(employee,year,cutoff,remaining,reason) VALUES(?,?,?,?,?) ON CONFLICT(employee,year) DO UPDATE SET cutoff=excluded.cutoff,remaining=excluded.remaining,reason=excluded.reason',(eid,year,cutoff,remaining,reason))
        after=balance(e,year)['available']
        current=db().execute('SELECT * FROM opening_balances WHERE employee=? AND year=?',(eid,year)).fetchone()
        audit('Actualizar saldo inicial',f'{eid} / {year}: anterior {dict(previous) if previous else None}; nuevo {dict(current) if current else None}; disponible {before} → {after}; motivo {reason}')
        commit_changes();return jsonify(ok=True,available=after)
    @app.post('/api/absences')
    @auth(True)
    def save_absence():
        p=request.get_json(); eid=int(p['employee']);year=int(p['year']);start=p['start'];end=p['end'];n=days(start,end);state=p['state'];kind=p['type'];aid=int(p.get('id') or 0)
        if not 1900<=year<=2200:raise ValueError('Período anual inválido.')
        if state not in STATES: raise ValueError('Estado inválido.')
        if not db().execute('SELECT 1 FROM types WHERE name=? AND active=1',(kind,)).fetchone(): raise ValueError('Tipo de ausencia inactivo o inexistente.')
        begin_write()
        e=db().execute('SELECT * FROM employees WHERE id=?',(eid,)).fetchone()
        if not e:raise ValueError('El empleado no existe.')
        if not e['active'] and state!='Disfrutadas' and (not aid or state not in ('Canceladas','Rechazadas')):raise ValueError('Seleccioná un empleado activo para registrar ausencias.')
        if start<e['hired']:raise ValueError('La ausencia no puede comenzar antes del ingreso.')
        old=db().execute('SELECT * FROM absences WHERE id=?',(aid,)).fetchone()
        if aid and not old:abort(404)
        requested=p.get('requested') or date.today().isoformat();approved=p.get('approved','');approver=p.get('approver','').strip()
        date.fromisoformat(requested)
        if approved:date.fromisoformat(approved)
        if state=='Disfrutadas' and end>date.today().isoformat():raise ValueError('Una ausencia futura no puede marcarse disfrutada.')
        if state=='Aprobadas' and (not approved or not approver):raise ValueError('Indicá fecha y responsable de aprobación.')
        if p.get('historical') and (kind!='Vacaciones' or state!='Disfrutadas' or end>date.today().isoformat()):raise ValueError('El historial debe ser de vacaciones ya disfrutadas, con fechas hasta hoy.')
        warnings=[]
        if state not in ('Rechazadas','Canceladas'):
            overlaps=db().execute("SELECT a.*,e.sector FROM absences a JOIN employees e ON e.id=a.employee WHERE a.id<>? AND a.state NOT IN ('Rechazadas','Canceladas') AND a.start<=? AND a.end>=?",(aid,end,start)).fetchall()
            if any(a['employee']==eid for a in overlaps):raise ValueError('El empleado ya tiene una ausencia en esas fechas.')
            if any(a['sector']==e['sector'] for a in overlaps):warnings.append('Coincide con ausencias de otras personas del mismo sector.')
            if kind=='Vacaciones':
                b=balance(e,year);available=b['available']
                cutoff=b['opening']['cutoff'] if b['opening'] else None
                n_charge=chargeable(start,end,cutoff)
                if old and old['employee']==eid and old['year']==year and old['type']=='Vacaciones' and old['state'] in ('Aprobadas','Disfrutadas'):available+=chargeable(old['start'],old['end'],cutoff)
                if n_charge>0 and n_charge>available:warnings.append(f"Este registro descuenta {n_charge} días y el saldo disponible es {available}.")
                if b['needs_review']:warnings.append('Antigüedad insuficiente para sugerir el período completo: RR. HH. debe confirmar días trabajados y asignación proporcional (1 día por cada 20 efectivamente trabajados, si corresponde).')
        if warnings and not p.get('confirm'):return jsonify(warnings=warnings),409
        values=(eid,kind,year,start,end,state,requested,approved,approver,p.get('notes','')[:2000])
        if aid:db().execute('UPDATE absences SET employee=?,type=?,year=?,start=?,end=?,state=?,requested=?,approved=?,approver=?,notes=? WHERE id=?',values+(aid,))
        else:aid=db().execute('INSERT INTO absences(employee,type,year,start,end,state,requested,approved,approver,notes) VALUES(?,?,?,?,?,?,?,?,?,?)',values).lastrowid
        audit('Guardar ausencia',f'{aid}: {kind}, {state}, {start} / {end}; días computables: {n_charge if kind=='Vacaciones' and state not in ('Rechazadas','Canceladas') else 0}; excepciones: {warnings}');commit_changes();return jsonify(id=aid)
    @app.post('/api/types')
    @auth(True)
    def save_type():
        p=request.get_json();name=required(p,'name');old=p.get('old')
        if old=='Vacaciones' or name=='Vacaciones':raise ValueError('El tipo Vacaciones está protegido.')
        if old and old!=name:
            db().execute('UPDATE types SET name=?,active=? WHERE name=?',(name,int(bool(p.get('active',True))),old));db().execute('UPDATE absences SET type=? WHERE type=?',(name,old))
        else:db().execute('INSERT INTO types VALUES(?,?) ON CONFLICT(name) DO UPDATE SET active=excluded.active',(name,int(bool(p.get('active',True)))))
        audit('Configurar tipo',name);commit_changes();return jsonify(ok=True)
    @app.post('/api/users')
    @auth(True)
    def user():
        p=request.get_json();validate_password(p['password'])
        if p['role'] not in ('admin','lectura'):raise ValueError('Rol inválido.')
        db().execute('INSERT INTO users(username,password,role) VALUES(?,?,?)',(required(p,'username'),generate_password_hash(p['password']),p['role']));audit('Crear usuario',p['username']);commit_changes();return jsonify(ok=True)
    @app.get('/api/users')
    @auth(True)
    def list_users():return jsonify([dict(r) for r in db().execute('SELECT id,username,role,active FROM users ORDER BY username')])
    @app.post('/api/users/manage')
    @auth(True)
    def manage_user():
        p=request.get_json();uid=int(p['id']);role=p['role'];active=1 if p.get('active') else 0
        if role not in ('admin','lectura'):raise ValueError('Rol inválido.')
        u=db().execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
        if not u:abort(404)
        if u['active'] and u['role']=='admin' and (not active or role!='admin'):
            if db().execute("SELECT count(*) FROM users WHERE active=1 AND role='admin'").fetchone()[0]<=1:raise ValueError('Debe quedar al menos un administrador activo.')
        password=p.get('password','')
        if password:validate_password(password)
        db().execute('UPDATE users SET role=?,active=?,password=? WHERE id=?',(role,active,generate_password_hash(password) if password else u['password'],uid))
        store.revoke(uid=uid);audit('Gestionar usuario',f'{uid}: rol {role}, activo {active}');commit_changes()
        return jsonify(ok=True)
    @app.post('/api/password')
    @auth()
    def password_change():
        p=request.get_json();u=current_user();validate_password(p.get('password'))
        if not check_password_hash(u['password'],p.get('current','')):abort(403,description='Contraseña actual incorrecta.')
        begin_write();db().execute('UPDATE users SET password=? WHERE id=?',(generate_password_hash(p['password']),u['id']))
        store.revoke(uid=u['id']);audit('Cambiar contraseña',u['id']);commit_changes();session.clear()
        return jsonify(ok=True)
    @app.cli.command('create-admin')
    @click.argument('username')
    def create_admin(username):
        """Crear administrador en consola. La contraseña se pide sin mostrarla."""
        password=click.prompt('Contraseña',hide_input=True,confirmation_prompt=True)
        validate_password(password);username=required({'username':username},'username')
        begin_write()
        if db().execute('SELECT 1 FROM users WHERE username=?',(username,)).fetchone():raise click.ClickException('El usuario ya existe. Usá reset-password para recuperar acceso.')
        db().execute("INSERT INTO users(username,password,role) VALUES(?,?,'admin')",(username,generate_password_hash(password)))
        audit('Crear administrador por consola',username);commit_changes();click.echo('Administrador creado.')
    @app.cli.command('reset-password')
    @click.argument('username')
    def reset_password(username):
        password=click.prompt('Contraseña',hide_input=True,confirmation_prompt=True)
        validate_password(password);begin_write()
        u=db().execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
        if not u:raise click.ClickException('El usuario no existe.')
        db().execute('UPDATE users SET password=? WHERE id=?',(generate_password_hash(password),u['id']))
        store.revoke(uid=u['id']);audit('Restablecer contraseña por consola',u['id']);commit_changes();click.echo('Contraseña restablecida y sesiones revocadas.')
    @app.get('/api/audit')
    @auth(True)
    def log():return jsonify([dict(r) for r in db().execute('SELECT * FROM audit ORDER BY id DESC LIMIT 200')])
    def opening_cutoff(a):
        row=db().execute('SELECT cutoff FROM opening_balances WHERE employee=? AND year=?',(a['employee'],a['year'])).fetchone()
        return row['cutoff'] if row else None
    def included_in_opening(a):
        cutoff=opening_cutoff(a)
        return days(a['start'],a['end'])-chargeable(a['start'],a['end'],cutoff) if cutoff and a['type']=='Vacaciones' else 0
    @app.get('/api/export')
    @auth()
    def export():
        year=int(request.args.get('year',date.today().year))
        if not 1900<=year<=2200:raise ValueError('Período anual inválido.')
        scope=request.args.get('scope','all')
        if scope not in ('all','vacations','leaves'):raise ValueError('Sección de exportación inválida.')
        wb=Workbook();ws=wb.active;ws.title='Empleados y saldos';ws.append(['Código','Nombre','Apellido','Sector','Puesto','Ingreso','Activo','Período','Asignados','Ajustes','Utilizados','Reservados','Disponibles','Saldo inicial real','Fecha de corte','Motivo saldo inicial','Utilizados incluidos en saldo inicial','Utilizados descontados','Adquiridos al cómputo','Fecha de cómputo','Proyección al cierre','Días computables','Origen cómputo','Días licencia año','Licencias utilizadas','Licencias reservadas','Licencias pendientes'])
        for e in db().execute('SELECT * FROM employees'):
            b=balance(e,year);leave=leave_summary(e['id'],year);ws.append([safe_cell(e[k]) for k in ['code','first','last','sector','position','hired']]+[e['active'],year]+[b[k] for k in ['assigned','adjustment','used','reserved','available']]+[b['opening']['remaining'] if b['opening'] else None,b['opening']['cutoff'] if b['opening'] else '',safe_cell(b['opening']['reason']) if b['opening'] else '',b['included_used'],b['deducted_used'],b['accrual']['acquired'],b['accrual']['asof'],b['accrual']['projected_closing'],b['accrual']['worked_days'],'Manual' if b['accrual']['manual'] else b['accrual']['source']]+[leave[k] for k in ['total','used','reserved','pending']])
        if scope=='leaves':
            wb.remove(ws);ws=wb.create_sheet('Resumen licencias');ws.append(['Código','Nombre','Apellido','Año calendario','Días utilizados','Días reservados','Pendientes','Total aprobado / disfrutado'])
            for e in db().execute('SELECT * FROM employees ORDER BY last,first'):
                leave=leave_summary(e['id'],year)
                ws.append([safe_cell(e[k]) for k in ['code','first','last']]+[year]+[leave[k] for k in ['used','reserved','pending','total']])
        elif scope=='vacations':
            ws.delete_cols(24,4)
        ws=wb.create_sheet('Ausencias');ws.append(['Empleado','Tipo','Período','Inicio','Fin','Días','Estado','Observaciones','Días incluidos en saldo inicial','Días computables posteriores al corte'])
        for a in db().execute('SELECT a.*,e.first,e.last FROM absences a JOIN employees e ON e.id=a.employee'):
            if scope=='vacations' and (a['type']!='Vacaciones' or a['year']!=year):continue
            if scope=='leaves' and (a['type']=='Vacaciones' or a['start']>f'{year}-12-31' or a['end']<f'{year}-01-01'):continue
            ws.append([safe_cell(f"{a['first']} {a['last']}"),safe_cell(a['type']),a['year'],a['start'],a['end'],days(a['start'],a['end']),a['state'],safe_cell(a['notes']),included_in_opening(a),chargeable(a['start'],a['end'],opening_cutoff(a)) if a['type']=='Vacaciones' else 0])
        out=io.BytesIO();wb.save(out);out.seek(0);return send_file(out,as_attachment=True,download_name=f'RRHH-{scope}-{year}.xlsx')
    def import_roster(upload,skip_existing=False):
        try:
            wb=load_workbook(upload,read_only=True,data_only=True)
        except Exception:raise ValueError('No se pudo leer el archivo. Usá un Excel .xlsx válido.')
        try:
            rows=iter(wb.active.values);header=list(next(rows,[]))
            expected=['code','first','last','sector','position','hired']
            if header[:6]!=expected:raise ValueError('Las primeras columnas deben ser: '+', '.join(expected))
            values=[]
            for number,row in enumerate(rows,2):
                if not any(v is not None and str(v).strip() for v in row):continue
                if number>5001:raise ValueError('Máximo 5000 filas por archivo.')
                p=dict(zip(expected,row[:6]));h=p.get('hired')
                if isinstance(h,datetime):p['hired']=h.date().isoformat()
                elif isinstance(h,date):p['hired']=h.isoformat()
                try:values.append(employee_values(p))
                except (ValueError,TypeError) as e:raise ValueError(f'Fila {number}: {e}')
        finally:wb.close()
        begin_write()
        count=skipped=0
        for value in values:
            if skip_existing and db().execute('SELECT 1 FROM employees WHERE code=?',(value[0],)).fetchone():
                skipped+=1;continue
            db().execute('INSERT INTO employees(code,first,last,sector,position,hired,active,notes) VALUES(?,?,?,?,?,?,?,?)',value);count+=1
        audit('Importar Excel',f'{count} agregados; {skipped} existentes omitidos')
        commit_changes();return dict(count=count,skipped=skipped)
    @app.post('/api/import')
    @auth(True)
    def import_excel():
        if 'file' not in request.files:raise ValueError('Seleccioná un Excel .xlsx.')
        try:return jsonify(import_roster(request.files['file'],request.form.get('skip_existing')=='1'))
        except (ValueError,sqlite3.IntegrityError):raise
        except Exception:raise ValueError('No se pudo importar el archivo. Revisá el formato y los datos.')
    @app.cli.command('import-roster')
    @click.argument('filename',type=click.Path(exists=True,dir_okay=False))
    @click.option('--skip-existing',is_flag=True,help='Omitir identificadores existentes sin modificarlos.')
    def import_roster_command(filename,skip_existing):
        """Importar una nómina local sin crear usuarios ni cambiar empleados existentes."""
        try:result=import_roster(filename,skip_existing)
        except (ValueError,sqlite3.IntegrityError) as e:raise click.ClickException(str(e)) from e
        click.echo(f"Empleados agregados: {result['count']}; existentes omitidos: {result['skipped']}.")
    @app.get('/api/backup')
    @auth(True)
    def backup():
        with tempfile.TemporaryDirectory(dir=root,prefix='.backup-') as temporary:
            snapshot=backup_database(app.config['DATABASE'],temporary)
            out=io.BytesIO(snapshot.read_bytes())
        return send_file(out,as_attachment=True,download_name=f'rrhh-{date.today()}.sqlite',mimetype='application/octet-stream')
    @app.post('/api/restore')
    @auth(True)
    def restore():
        if settings.production:abort(403,description='Sistemas debe restaurar con el servicio detenido mediante manage.py.')
        if request.form.get('confirm')!='RESTAURAR':raise ValueError('Escribí RESTAURAR para confirmar.')
        password=request.form.get('password','');u=db().execute('SELECT * FROM users WHERE id=?',(session['uid'],)).fetchone()
        if not check_password_hash(u['password'],password):abort(403,description='Contraseña incorrecta.')
        blob=request.files['file'].read();candidate=sqlite3.connect(':memory:')
        try:
            with tempfile.TemporaryDirectory(dir=root,prefix='.restore-') as temporary:
                uploaded=Path(temporary)/'uploaded.sqlite';uploaded.write_bytes(blob);uploaded.chmod(0o600)
                with closing(sqlite3.connect(uploaded)) as source:source.backup(candidate)
            prepare_candidate(candidate)
            current=db()
            if not candidate.execute("SELECT 1 FROM users WHERE role='admin' AND active=1").fetchone():raise ValueError('La copia no contiene administrador activo.')
            backup_database(app.config['DATABASE'],root,'antes-restaurar')
            candidate.backup(current);audit('Restaurar copia');commit_changes()
            store.revoke();session.clear()
        except sqlite3.Error:raise ValueError('El archivo no es una copia SQLite válida.')
        finally:candidate.close()
        return jsonify(ok=True)
    @app.post('/api/demo')
    @auth(True)
    def demo():
        if settings.production:abort(403,description='La demostración está deshabilitada en producción.')
        p=request.get_json()
        if p.get('delete'):
            if p.get('confirm')!='ELIMINAR DEMO':raise ValueError('Confirmación requerida.')
            db().execute('DELETE FROM accruals WHERE employee IN (SELECT id FROM employees WHERE demo=1)')
            db().execute('DELETE FROM opening_balances WHERE employee IN (SELECT id FROM employees WHERE demo=1)')
            db().execute('DELETE FROM absences WHERE employee IN (SELECT id FROM employees WHERE demo=1)');db().execute('DELETE FROM balances WHERE employee IN (SELECT id FROM employees WHERE demo=1)');db().execute('DELETE FROM employees WHERE demo=1');audit('Eliminar demo')
        else:
            if db().execute('SELECT 1 FROM employees WHERE demo=1').fetchone():raise ValueError('Los datos de demostración ya están cargados.')
            today=date.today(); start=today.replace(day=5);end=today.replace(day=12)
            for i,(first,last,sector) in enumerate([('Lucía','Pérez','Administración'),('Martín','Gómez','Ventas'),('Sofía','Torres','Administración'),('Diego','Ruiz','Operaciones')],1):
                eid=db().execute("INSERT INTO employees(code,first,last,sector,position,hired,demo) VALUES(?,?,?,?,?,'2018-03-01',1)",(f'DEMO-{i}',first,last,sector,'Analista')).lastrowid
                db().execute("INSERT INTO absences(employee,type,year,start,end,state,requested,approved,approver) VALUES(?,?,?,?,?,'Aprobadas',?,?,?)",(eid,'Vacaciones' if i%2 else 'Estudio',today.year,(start+timedelta(days=i)).isoformat(),(end+timedelta(days=i)).isoformat(),today.isoformat(),today.isoformat(),'Demo RR. HH.'))
            audit('Cargar demo')
        commit_changes();return jsonify(ok=True)
    return app

def required(p,key):
    value=str(p.get(key) or '').strip()
    if not value:raise ValueError(f'Completá el campo {key}.')
    if len(value)>200:raise ValueError('El campo es demasiado largo.')
    return value

def validate_password(value):
    if not isinstance(value,str) or len(value)<12:raise ValueError('La contraseña debe tener al menos 12 caracteres.')

def safe_cell(value):
    return "'"+value if isinstance(value,str) and value.startswith(('=','+','-','@')) else value

if __name__=='__main__':
    from run_server import main
    main()
