import io, tempfile, unittest
from datetime import date, timedelta
from openpyxl import Workbook, load_workbook
from app import create_app, suggested, days

class AppTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.app=create_app(self.tmp.name);self.app.testing=True;self.c=self.app.test_client();self.c.get('/')
        with self.c.session_transaction() as s:self.csrf=s['csrf']
        self.post('setup',dict(username='admin',password='contraseña-segura-123'))
        self.post('login',dict(username='admin',password='contraseña-segura-123'))
        self.year=date.today().year
        r=self.post('employees',dict(code='E1',first='Ana',last='Pérez',sector='Ventas',position='Analista',hired='2010-01-01',active=True));self.eid=r.json['id']
    def tearDown(self):self.tmp.cleanup()
    def post(self,path,p):return self.c.post('/api/'+path,json=p,headers={'X-CSRF-Token':self.csrf})
    def data(self):return self.c.get('/api/data?year='+str(self.year)).json
    def absence(self,**kw):
        start=date(self.year,1,5);p=dict(employee=self.eid,type='Vacaciones',year=self.year,start=start.isoformat(),end=(start+timedelta(days=3)).isoformat(),state='Aprobadas',requested=date.today().isoformat(),approved=date.today().isoformat(),approver='RRHH');p.update(kw);return self.post('absences',p)
    def test_legal_boundaries(self):
        for hired,n in [('2020-12-31',14),('2019-12-31',21),('2015-12-31',21),('2014-12-31',28),('2005-12-31',28),('2004-12-31',35)]:self.assertEqual(suggested(hired,2025),n)
        self.assertIsNone(suggested('2025-07-01',2025));self.assertEqual(days('2024-02-28','2024-03-01'),3)
    def test_balances_states_years_and_cancellation(self):
        self.assertEqual(self.post('balances',dict(employee=self.eid,year=self.year,assigned=20,adjustment=2,reason='Saldo inicial validado')).status_code,200)
        a=self.absence(state='Solicitadas');self.assertEqual(a.status_code,200);self.assertEqual(self.data()['employees'][0]['balance']['available'],22)
        a=self.absence(id=a.json['id']);self.assertEqual(a.status_code,200)
        b=self.data()['employees'][0]['balance'];self.assertEqual(b['used']+b['reserved'],4);self.assertEqual(b['available'],18)
        self.assertEqual(self.absence().status_code,400)
        self.assertEqual(self.absence(id=a.json['id'],state='Canceladas').status_code,200);self.assertEqual(self.data()['employees'][0]['balance']['available'],22)
        self.post('balances',dict(employee=self.eid,year=self.year-1,assigned=99,reason='Anterior'));self.assertEqual(self.data()['employees'][0]['balance']['assigned'],20)
    def test_exception_and_leave(self):
        self.post('balances',dict(employee=self.eid,year=self.year,assigned=0,reason='Sin saldo'))
        r=self.absence();self.assertEqual(r.status_code,409);self.assertTrue(r.json['warnings'])
        self.assertEqual(self.absence(confirm=True).status_code,200)
        r=self.absence(type='Estudio',start=f'{self.year}-02-01',end=f'{self.year}-02-03');self.assertEqual(r.status_code,200)
        self.assertEqual(self.data()['employees'][0]['balance']['available'],-4)
    def test_roles_csrf_and_auth(self):
        self.assertEqual(self.c.post('/api/employees',json={}).status_code,400)
        self.post('users',dict(username='gerencia',password='otra-clave-segura',role='lectura'))
        self.post('logout',{});self.c.get('/')
        with self.c.session_transaction() as s:self.csrf=s['csrf']
        self.assertEqual(self.c.get('/api/data').status_code,401)
        self.post('login',dict(username='gerencia',password='otra-clave-segura'))
        self.assertEqual(self.c.get('/api/data').status_code,200)
        for path in ['employees','absences','balances','users','types','demo','restore','import']:self.assertEqual(self.post(path,{}).status_code,403,path)
        self.assertEqual(self.c.get('/api/backup').status_code,403)
    def test_excel_atomic_import_export(self):
        wb=Workbook();ws=wb.active;ws.append(['code','first','last','sector','position','hired']);ws.append(['E2','Luz','Ruiz','Ventas','Analista','2020-01-01']);ws.append(['E1','Otra','Ruiz','Ventas','Analista','2020-01-01']);out=io.BytesIO();wb.save(out);out.seek(0)
        r=self.c.post('/api/import',data={'file':(out,'empleados.xlsx')},headers={'X-CSRF-Token':self.csrf});self.assertEqual(r.status_code,400);self.assertEqual(len(self.data()['employees']),1)
        r=self.c.get('/api/export');self.assertEqual(r.status_code,200);book=load_workbook(io.BytesIO(r.data));self.assertEqual(book.active.max_row,2)
    def test_persistence_backup_restore_and_demo(self):
        backup=self.c.get('/api/backup');self.assertEqual(backup.status_code,200)
        self.assertEqual(self.post('demo',{}).status_code,200);self.assertEqual(len(self.data()['employees']),5)
        self.assertEqual(self.post('demo',dict(delete=True,confirm='ELIMINAR DEMO')).status_code,200);self.assertEqual(len(self.data()['employees']),1)
        self.post('employees',dict(code='E9',first='Nueva',last='Persona',sector='RRHH',position='Analista',hired='2020-01-01'))
        r=self.c.post('/api/restore',data={'file':(io.BytesIO(backup.data),'backup.sqlite'),'confirm':'RESTAURAR','password':'contraseña-segura-123'},headers={'X-CSRF-Token':self.csrf});self.assertEqual(r.status_code,200)
        new=create_app(self.tmp.name).test_client();new.get('/')
        with new.session_transaction() as s:token=s['csrf']
        new.post('/api/login',json=dict(username='admin',password='contraseña-segura-123'),headers={'X-CSRF-Token':token});self.assertEqual(len(new.get('/api/data').json['employees']),1)
    def test_future_used_invalid_dates_and_inactive(self):
        future=(date.today()+timedelta(days=30)).isoformat();self.assertEqual(self.absence(start=future,end=future,state='Disfrutadas').status_code,400)
        self.assertEqual(self.absence(start='incorrecta').status_code,400)
        self.assertEqual(self.absence(approved='',approver='').status_code,400)
    def test_future_reservations_rejections_and_inactive_cancellation(self):
        start=date.today()+timedelta(days=60)
        r=self.absence(start=start.isoformat(),end=(start+timedelta(days=4)).isoformat())
        self.assertEqual(r.status_code,200)
        b=self.data()['employees'][0]['balance'];self.assertEqual(b['reserved'],5);self.assertEqual(b['used'],0)
        self.assertEqual(self.absence(id=r.json['id'],start=start.isoformat(),end=(start+timedelta(days=4)).isoformat(),state='Rechazadas').status_code,200)
        self.assertEqual(self.data()['employees'][0]['balance']['reserved'],0)
        self.post('employees',dict(id=self.eid,code='E1',first='Ana',last='Pérez',sector='Ventas',position='Analista',hired='2010-01-01',active=False))
        self.assertEqual(self.absence(id=r.json['id'],state='Canceladas').status_code,200)
        self.assertEqual(self.c.get('/api/data?year=0').status_code,400)

    def test_type_management_and_formula_export(self):
        self.assertEqual(self.post('types',dict(name='Donación',active=True)).status_code,200)
        self.assertEqual(self.post('types',dict(old='Donación',name='Donación de sangre',active=False)).status_code,200)
        self.assertEqual(self.post('types',dict(name='Vacaciones',active=False)).status_code,400)
        self.post('employees',dict(code='=1+1',first='Luz',last='Prueba',sector='Ventas',position='Test',hired='2020-01-01'))
        book=load_workbook(io.BytesIO(self.c.get('/api/export').data));self.assertEqual(book.active.cell(3,1).data_type,'s')

if __name__=='__main__':unittest.main()
