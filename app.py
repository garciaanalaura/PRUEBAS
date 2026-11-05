from __future__ import annotations
import calendar, io, os, secrets, sqlite3
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path
from flask import Flask, abort, g, jsonify, render_template, request, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from openpyxl import Workbook, load_workbook

TYPES = ['Vacaciones','Enfermedad','Estudio','Maternidad','Paternidad','Matrimonio','Fallecimiento de familiar','Trámites personales','Otras']
STATES = ['Solicitadas','Aprobadas','Rechazadas','Canceladas','Disfrutadas']
SCHEMA = '''
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','lectura')));
CREATE TABLE IF NOT EXISTS employees(id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, first TEXT NOT NULL, last TEXT NOT NULL, sector TEXT NOT NULL, position TEXT NOT NULL, hired TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, notes TEXT NOT NULL DEFAULT '', demo INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS balances(employee INTEGER REFERENCES employees(id), year INTEGER NOT NULL, assigned REAL NOT NULL, adjustment REAL NOT NULL DEFAULT 0, reason TEXT NOT NULL DEFAULT '', PRIMARY KEY(employee,year));
CREATE TABLE IF NOT EXISTS absences(id INTEGER PRIMARY KEY, employee INTEGER NOT NULL REFERENCES employees(id), type TEXT NOT NULL, year INTEGER NOT NULL, start TEXT NOT NULL, end TEXT NOT NULL, state TEXT NOT NULL, requested TEXT NOT NULL, approved TEXT NOT NULL DEFAULT '', approver TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS types(name TEXT PRIMARY KEY, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, at TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL);
'''

def suggested(hired, year):
    start = date.fromisoformat(hired); cutoff = date(year,12,31)
    if start > cutoff: return None
    # Employment duration alone does not establish the days actually worked (LCT arts. 151/153).
    if start > date(year,1,1): return None
    years = cutoff.year-start.year-((cutoff.month,cutoff.day)<(start.month,start.day))
    return 14 if years <= 5 else 21 if years <= 10 else 28 if years <= 20 else 35

def days(start,end):
    a,b=date.fromisoformat(start),date.fromisoformat(end)
    if b<a: raise ValueError('La fecha final debe ser igual o posterior al inicio.')
    return (b-a).days+1

def create_app(data_dir=None):
    app=Flask(__name__)
    root=Path(data_dir or os.environ.get('RRHH_DATA',Path(__file__).parent/'data')); root.mkdir(parents=True,exist_ok=True)
    key=root/'session.key'
    if not key.exists(): key.write_text(secrets.token_hex(32)); key.chmod(0o600)
    app.config.update(SECRET_KEY=key.read_text(),DATABASE=str(root/'rrhh.sqlite'),MAX_CONTENT_LENGTH=10*1024*1024,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SECURE=os.environ.get('RRHH_HTTPS')=='1',SESSION_COOKIE_SAMESITE='Strict',PERMANENT_SESSION_LIFETIME=timedelta(hours=8))
    def db():
        if 'db' not in g:
            g.db=sqlite3.connect(app.config['DATABASE'],timeout=15); g.db.row_factory=sqlite3.Row; g.db.execute('PRAGMA foreign_keys=ON')
        return g.db
    @app.teardown_appcontext
    def close(_):
        if 'db' in g: g.db.close()
    with app.app_context():
        db().executescript(SCHEMA)
        db().executemany('INSERT OR IGNORE INTO types(name) VALUES(?)',[(t,) for t in TYPES]);db().commit()
    def audit(action,detail=''):
        db().execute('INSERT INTO audit(at,actor,action,detail) VALUES(?,?,?,?)',(datetime.now().isoformat(timespec='seconds'),session.get('username','Inicialización'),action,str(detail)))
    def auth(admin=False):
        def deco(fn):
            @wraps(fn)
            def wrapped(*a,**kw):
                u=db().execute('SELECT * FROM users WHERE id=?',(session.get('uid'),)).fetchone()
                if not u: abort(401)
                if admin and u['role']!='admin': abort(403)
                return fn(*a,**kw)
            return wrapped
        return deco
    @app.before_request
    def csrf():
        if 'csrf' not in session: session['csrf']=secrets.token_hex(24)
        if request.method in ('POST','PUT','DELETE') and request.headers.get('X-CSRF-Token')!=session['csrf']: abort(400,description='Sesión vencida. Recargá la página.')
    @app.after_request
    def headers(r):
        r.headers['X-Content-Type-Options']='nosniff';r.headers['X-Frame-Options']='DENY';r.headers['Cache-Control']='no-store'
        r.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return r
    @app.errorhandler(ValueError)
    def invalid(e): return jsonify(error=str(e)),400
    @app.errorhandler(sqlite3.IntegrityError)
    def conflict(e): return jsonify(error='El identificador o usuario ya existe, o el registro tiene referencias.'),400
    from werkzeug.exceptions import HTTPException
    @app.errorhandler(HTTPException)
    def http_error(e): return jsonify(error=e.description),e.code
    @app.get('/')
    def index(): return render_template('index.html',csrf=session['csrf'])
    @app.get('/api/session')
    def who(): return jsonify(user=session.get('username'),role=session.get('role'),setup=not db().execute('SELECT 1 FROM users').fetchone())
    @app.post('/api/setup')
    def setup():
        # Serialize first-user creation to prevent two simultaneous administrators.
        db().execute('BEGIN IMMEDIATE')
        if db().execute('SELECT 1 FROM users').fetchone(): abort(403)
        p=request.get_json(); validate_password(p['password'])
        username=required(p,'username')
        db().execute('INSERT INTO users(username,password,role) VALUES(?,?,?)',(username,generate_password_hash(p['password']),'admin'));audit('Crear administrador');db().commit()
        return jsonify(ok=True)
    attempts={}
    @app.post('/api/login')
    def login():
        ip=request.remote_addr; now=datetime.now().timestamp(); recent=[t for t in attempts.get(ip,[]) if now-t<300]
        if len(recent)>=10: abort(429,description='Demasiados intentos. Esperá cinco minutos.')
        p=request.get_json(); u=db().execute('SELECT * FROM users WHERE username=?',(p.get('username'),)).fetchone()
        if not u or not check_password_hash(u['password'],p.get('password','')):
            attempts[ip]=recent+[now];abort(401,description='Usuario o contraseña incorrectos.')
        session.update(uid=u['id'],username=u['username'],role=u['role']);session.permanent=True;attempts.pop(ip,None)
        return jsonify(ok=True)
    @app.post('/api/logout')
    def logout(): session.clear();return jsonify(ok=True)
    def balance(e,year):
        row=db().execute('SELECT * FROM balances WHERE employee=? AND year=?',(e['id'],year)).fetchone()
        suggestion=suggested(e['hired'],year); assigned=row['assigned'] if row else (suggestion or 0); adjustment=row['adjustment'] if row else 0
        used=reserved=0
        for a in db().execute("SELECT * FROM absences WHERE employee=? AND year=? AND type='Vacaciones'",(e['id'],year)):
            n=days(a['start'],a['end'])
            if a['state']=='Disfrutadas' or (a['state']=='Aprobadas' and a['end']<date.today().isoformat()): used+=n
            elif a['state']=='Aprobadas': reserved+=n
        return dict(assigned=assigned,adjustment=adjustment,reason=row['reason'] if row else '',used=used,reserved=reserved,available=assigned+adjustment-used-reserved,suggested=suggestion,needs_review=suggestion is None and row is None)
    @app.get('/api/data')
    @auth()
    def data():
        year=int(request.args.get('year',date.today().year))
        if not 1900<=year<=2200:raise ValueError('Período anual inválido.')
        employees=[]
        for e in db().execute('SELECT * FROM employees ORDER BY last,first'):
            item=dict(e);item['balance']=balance(e,year);item['seniority']=max(0,(date.today()-date.fromisoformat(e['hired'])).days//365);employees.append(item)
        absences=[dict(a,days=days(a['start'],a['end'])) for a in db().execute('SELECT * FROM absences ORDER BY start')]
        today=date.today(); current=today.replace(day=1); following=(current.replace(day=28)+timedelta(days=4)).replace(day=1); after=(following.replace(day=28)+timedelta(days=4)).replace(day=1)
        def count(a,b):return len({r['employee'] for r in absences if r['type']=='Vacaciones' and r['state'] in ('Aprobadas','Disfrutadas') and r['start']<b.isoformat() and r['end']>=a.isoformat()})
        return jsonify(employees=employees,absences=absences,types=[dict(t) for t in db().execute('SELECT * FROM types ORDER BY name')],stats=dict(active=sum(e['active'] for e in employees),current=count(current,following),next=count(following,after)),today=today.isoformat())
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
        audit('Guardar empleado',eid);db().commit();return jsonify(id=eid)
    @app.post('/api/balances')
    @auth(True)
    def save_balance():
        p=request.get_json();assigned=float(p['assigned']);adjustment=float(p.get('adjustment',0));year=int(p['year'])
        import math
        if not math.isfinite(assigned) or not math.isfinite(adjustment) or assigned<0 or not 1900<=year<=2200:raise ValueError('Saldo o período inválido.')
        reason=required(p,'reason')
        db().execute('INSERT INTO balances VALUES(?,?,?,?,?) ON CONFLICT(employee,year) DO UPDATE SET assigned=excluded.assigned,adjustment=excluded.adjustment,reason=excluded.reason',(int(p['employee']),year,assigned,adjustment,reason));audit('Ajustar saldo',f"{p['employee']} / {year}: asignados {assigned}, ajuste {adjustment}, motivo {reason}");db().commit();return jsonify(ok=True)
    @app.post('/api/absences')
    @auth(True)
    def save_absence():
        p=request.get_json(); eid=int(p['employee']);year=int(p['year']);start=p['start'];end=p['end'];n=days(start,end);state=p['state'];kind=p['type'];aid=int(p.get('id') or 0)
        if not 1900<=year<=2200:raise ValueError('Período anual inválido.')
        if state not in STATES: raise ValueError('Estado inválido.')
        if not db().execute('SELECT 1 FROM types WHERE name=? AND active=1',(kind,)).fetchone(): raise ValueError('Tipo de ausencia inactivo o inexistente.')
        db().execute('BEGIN IMMEDIATE')
        e=db().execute('SELECT * FROM employees WHERE id=?',(eid,)).fetchone()
        if not e:raise ValueError('El empleado no existe.')
        if not e['active'] and (not aid or state not in ('Canceladas','Rechazadas')):raise ValueError('Seleccioná un empleado activo para registrar ausencias.')
        if start<e['hired']:raise ValueError('La ausencia no puede comenzar antes del ingreso.')
        old=db().execute('SELECT * FROM absences WHERE id=?',(aid,)).fetchone()
        if aid and not old:abort(404)
        requested=p.get('requested') or date.today().isoformat();approved=p.get('approved','');approver=p.get('approver','').strip()
        date.fromisoformat(requested)
        if approved:date.fromisoformat(approved)
        if state=='Disfrutadas' and end>date.today().isoformat():raise ValueError('Una ausencia futura no puede marcarse disfrutada.')
        if state=='Aprobadas' and (not approved or not approver):raise ValueError('Indicá fecha y responsable de aprobación.')
        warnings=[]
        if state not in ('Rechazadas','Canceladas'):
            overlaps=db().execute("SELECT a.*,e.sector FROM absences a JOIN employees e ON e.id=a.employee WHERE a.id<>? AND a.state NOT IN ('Rechazadas','Canceladas') AND a.start<=? AND a.end>=?",(aid,end,start)).fetchall()
            if any(a['employee']==eid for a in overlaps):raise ValueError('El empleado ya tiene una ausencia en esas fechas.')
            if any(a['sector']==e['sector'] for a in overlaps):warnings.append('Coincide con ausencias de otras personas del mismo sector.')
            if kind=='Vacaciones':
                b=balance(e,year);available=b['available']
                if old and old['employee']==eid and old['year']==year and old['type']=='Vacaciones' and old['state'] in ('Aprobadas','Disfrutadas'):available+=days(old['start'],old['end'])
                if n>available:warnings.append(f"Solicitás {n} días y el saldo disponible es {available}.")
                if b['needs_review']:warnings.append('Antigüedad insuficiente para sugerir el período completo: RR. HH. debe confirmar días trabajados y asignación proporcional (1 día por cada 20 efectivamente trabajados, si corresponde).')
        if warnings and not p.get('confirm'):return jsonify(warnings=warnings),409
        values=(eid,kind,year,start,end,state,requested,approved,approver,p.get('notes','')[:2000])
        if aid:db().execute('UPDATE absences SET employee=?,type=?,year=?,start=?,end=?,state=?,requested=?,approved=?,approver=?,notes=? WHERE id=?',values+(aid,))
        else:aid=db().execute('INSERT INTO absences(employee,type,year,start,end,state,requested,approved,approver,notes) VALUES(?,?,?,?,?,?,?,?,?,?)',values).lastrowid
        audit('Guardar ausencia',f'{aid}: {kind}, {state}, {start} / {end}; excepciones: {warnings}');db().commit();return jsonify(id=aid)
    @app.post('/api/types')
    @auth(True)
    def save_type():
        p=request.get_json();name=required(p,'name');old=p.get('old')
        if old=='Vacaciones' or name=='Vacaciones':raise ValueError('El tipo Vacaciones está protegido.')
        if old and old!=name:
            db().execute('UPDATE types SET name=?,active=? WHERE name=?',(name,int(bool(p.get('active',True))),old));db().execute('UPDATE absences SET type=? WHERE type=?',(name,old))
        else:db().execute('INSERT INTO types VALUES(?,?) ON CONFLICT(name) DO UPDATE SET active=excluded.active',(name,int(bool(p.get('active',True)))))
        audit('Configurar tipo',name);db().commit();return jsonify(ok=True)
    @app.post('/api/users')
    @auth(True)
    def user():
        p=request.get_json();validate_password(p['password'])
        if p['role'] not in ('admin','lectura'):raise ValueError('Rol inválido.')
        db().execute('INSERT INTO users(username,password,role) VALUES(?,?,?)',(required(p,'username'),generate_password_hash(p['password']),p['role']));audit('Crear usuario',p['username']);db().commit();return jsonify(ok=True)
    @app.get('/api/audit')
    @auth(True)
    def log():return jsonify([dict(r) for r in db().execute('SELECT * FROM audit ORDER BY id DESC LIMIT 200')])
    @app.get('/api/export')
    @auth()
    def export():
        year=int(request.args.get('year',date.today().year))
        if not 1900<=year<=2200:raise ValueError('Período anual inválido.')
        wb=Workbook();ws=wb.active;ws.title='Empleados y saldos';ws.append(['Código','Nombre','Apellido','Sector','Puesto','Ingreso','Activo','Período','Asignados','Ajustes','Utilizados','Reservados','Disponibles'])
        for e in db().execute('SELECT * FROM employees'):
            b=balance(e,year);ws.append([safe_cell(e[k]) for k in ['code','first','last','sector','position','hired']]+[e['active'],year]+[b[k] for k in ['assigned','adjustment','used','reserved','available']])
        ws=wb.create_sheet('Ausencias');ws.append(['Empleado','Tipo','Período','Inicio','Fin','Días','Estado','Observaciones'])
        for a in db().execute('SELECT a.*,e.first,e.last FROM absences a JOIN employees e ON e.id=a.employee'):
            ws.append([safe_cell(f"{a['first']} {a['last']}"),safe_cell(a['type']),a['year'],a['start'],a['end'],days(a['start'],a['end']),a['state'],safe_cell(a['notes'])])
        out=io.BytesIO();wb.save(out);out.seek(0);return send_file(out,as_attachment=True,download_name=f'RRHH-{year}.xlsx')
    @app.post('/api/import')
    @auth(True)
    def import_excel():
        try:
            wb=load_workbook(request.files['file'],read_only=True,data_only=True);ws=wb.active;rows=iter(ws.values)
            expected=['code','first','last','sector','position','hired'];header=list(next(rows))
            if header[:6]!=expected:raise ValueError('Las primeras columnas deben ser: '+', '.join(expected))
            count=0
            for number,row in enumerate(rows,2):
                if not any(row):continue
                if number>5001:raise ValueError('Máximo 5000 empleados por archivo.')
                p=dict(zip(expected,row[:6]));h=p['hired']
                if isinstance(h,datetime):p['hired']=h.date().isoformat()
                elif isinstance(h,date):p['hired']=h.isoformat()
                try:values=employee_values(p)
                except (ValueError,TypeError) as e:raise ValueError(f'Fila {number}: {e}')
                db().execute('INSERT INTO employees(code,first,last,sector,position,hired,active,notes) VALUES(?,?,?,?,?,?,?,?)',values);count+=1
            audit('Importar Excel',count);db().commit();return jsonify(count=count)
        except (ValueError,sqlite3.IntegrityError):raise
        except Exception:raise ValueError('No se pudo leer el archivo. Usá un Excel .xlsx válido con las columnas indicadas.')
    @app.get('/api/backup')
    @auth(True)
    def backup():
        out=io.BytesIO(db().serialize());return send_file(out,as_attachment=True,download_name=f'rrhh-{date.today()}.sqlite',mimetype='application/octet-stream')
    @app.post('/api/restore')
    @auth(True)
    def restore():
        if request.form.get('confirm')!='RESTAURAR':raise ValueError('Escribí RESTAURAR para confirmar.')
        password=request.form.get('password','');u=db().execute('SELECT * FROM users WHERE id=?',(session['uid'],)).fetchone()
        if not check_password_hash(u['password'],password):abort(403,description='Contraseña incorrecta.')
        blob=request.files['file'].read();candidate=sqlite3.connect(':memory:')
        try:
            candidate.deserialize(blob)
            if candidate.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Copia dañada.')
            current=db()
            for table in ['users','employees','balances','absences','types','audit']:
                wanted=[r[1:3] for r in current.execute(f'PRAGMA table_info({table})')];actual=[r[1:3] for r in candidate.execute(f'PRAGMA table_info({table})')]
                if actual!=wanted:raise ValueError('La copia no es compatible con esta versión.')
            if candidate.execute('PRAGMA foreign_key_check').fetchone():raise ValueError('La copia contiene referencias inválidas.')
            if not candidate.execute("SELECT 1 FROM users WHERE role='admin'").fetchone():raise ValueError('La copia no contiene administrador.')
            backup_path=root/f"antes-restaurar-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.sqlite"
            with sqlite3.connect(backup_path) as saved:current.backup(saved)
            candidate.backup(current);audit('Restaurar copia');current.commit()
            key.write_text(secrets.token_hex(32));key.chmod(0o600);app.config['SECRET_KEY']=key.read_text();session.clear()
        except sqlite3.Error:raise ValueError('El archivo no es una copia SQLite válida.')
        finally:candidate.close()
        return jsonify(ok=True)
    @app.post('/api/demo')
    @auth(True)
    def demo():
        p=request.get_json()
        if p.get('delete'):
            if p.get('confirm')!='ELIMINAR DEMO':raise ValueError('Confirmación requerida.')
            db().execute('DELETE FROM absences WHERE employee IN (SELECT id FROM employees WHERE demo=1)');db().execute('DELETE FROM balances WHERE employee IN (SELECT id FROM employees WHERE demo=1)');db().execute('DELETE FROM employees WHERE demo=1');audit('Eliminar demo')
        else:
            if db().execute('SELECT 1 FROM employees WHERE demo=1').fetchone():raise ValueError('Los datos de demostración ya están cargados.')
            today=date.today(); start=today.replace(day=5);end=today.replace(day=12)
            for i,(first,last,sector) in enumerate([('Lucía','Pérez','Administración'),('Martín','Gómez','Ventas'),('Sofía','Torres','Administración'),('Diego','Ruiz','Operaciones')],1):
                eid=db().execute("INSERT INTO employees(code,first,last,sector,position,hired,demo) VALUES(?,?,?,?,?,'2018-03-01',1)",(f'DEMO-{i}',first,last,sector,'Analista')).lastrowid
                db().execute("INSERT INTO absences(employee,type,year,start,end,state,requested,approved,approver) VALUES(?,?,?,?,?,'Aprobadas',?,?,?)",(eid,'Vacaciones' if i%2 else 'Estudio',today.year,(start+timedelta(days=i)).isoformat(),(end+timedelta(days=i)).isoformat(),today.isoformat(),today.isoformat(),'Demo RR. HH.'))
            audit('Cargar demo')
        db().commit();return jsonify(ok=True)
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
    from waitress import serve
    print('Gestión de personas: http://127.0.0.1:8080 — Ctrl+C para cerrar')
    serve(create_app(),host=os.environ.get('RRHH_HOST','127.0.0.1'),port=int(os.environ.get('RRHH_PORT','8080')),threads=4)
