import io, tempfile, unittest
from datetime import date, timedelta
from openpyxl import Workbook, load_workbook
from app import create_app, suggested, days, accrual_estimate

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
        for path in ['employees','absences','balances','accruals','users','types','demo','restore','import']:self.assertEqual(self.post(path,{}).status_code,403,path)
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

    def test_acquired_today_and_closing_projection(self):
        a=accrual_estimate('2026-10-08',2026,'2026-11-06')
        self.assertEqual(a['estimated_workdays'],22)
        self.assertEqual(a['estimated_acquired'],1)
        self.assertEqual(a['projected_closing'],3)
        self.assertEqual(a['full_entitlement'],14)
        self.assertEqual(accrual_estimate('2026-10-08',2026,'2026-11-06',19)['estimated_acquired'],0)
        self.assertEqual(accrual_estimate('2026-10-08',2026,'2026-11-06',20)['estimated_acquired'],1)
        self.assertEqual(accrual_estimate('2026-10-08',2026,'2026-11-06',40)['estimated_acquired'],2)
    def test_acquired_threshold_and_year_boundaries(self):
        a=accrual_estimate('2010-01-01',2026,'2026-11-06')
        threshold=a['half_year_threshold']
        self.assertEqual(accrual_estimate('2010-01-01',2026,'2026-11-06',threshold)['estimated_acquired'],28)
        self.assertEqual(accrual_estimate('2010-01-01',2026,'2026-11-06',threshold-1)['estimated_acquired'],(threshold-1)//20)
        self.assertEqual(accrual_estimate('2027-01-01',2027,'2026-11-06')['estimated_acquired'],0)
        self.assertEqual(accrual_estimate('2026-10-08',2026,'2027-11-06')['asof'],'2026-12-31')
        self.assertEqual(accrual_estimate('2026-10-08',2025,'2026-11-06')['projected_closing'],0)
    def test_manual_acquired_is_separate_from_assignment_and_year(self):
        before=self.data()['employees'][0]['balance']['available']
        p=dict(employee=self.eid,year=self.year,asof=date.today().isoformat(),worked_days=20,acquired=2,reason='Validado por RRHH')
        self.assertEqual(self.post('accruals',p).status_code,200)
        b=self.data()['employees'][0]['balance'];self.assertEqual(b['accrual']['acquired'],2);self.assertTrue(b['accrual']['manual']);self.assertEqual(b['available'],before)
        self.assertEqual(self.post('accruals',{**p,'assigned':1}).status_code,200)
        b=self.data()['employees'][0]['balance'];self.assertEqual(b['available'],1);self.assertEqual(b['assigned'],1)
        self.assertIsNone(self.c.get('/api/data?year='+str(self.year-1)).json['employees'][0]['balance']['accrual']['record'])
        self.assertEqual(self.post('accruals',{**p,'acquired':0,'assigned':0}).status_code,200)
        self.assertEqual(self.data()['employees'][0]['balance']['accrual']['acquired'],0)
        self.assertEqual(self.post('accruals',{**p,'reset':True,'assigned':''}).status_code,200)
        b=self.data()['employees'][0]['balance'];self.assertIsNone(b['accrual']['record']);self.assertEqual(b['assigned'],0)
    def test_computable_days_manual_clear_and_validation(self):
        p=dict(employee=self.eid,year=self.year,asof=date.today().isoformat(),worked_days=20,acquired='',reason='Días confirmados')
        self.assertEqual(self.post('accruals',p).status_code,200)
        self.assertEqual(self.data()['employees'][0]['balance']['accrual']['acquired'],1)
        for bad in [dict(worked_days=-1),dict(worked_days=20.5),dict(worked_days=99999),dict(acquired='NaN'),dict(assigned=-1),dict(reason=''),dict(asof='2000-01-01'),dict(year=0),dict(asof=(date.today()+timedelta(days=1)).isoformat())]:
            self.assertEqual(self.post('accruals',{**p,**bad}).status_code,400,bad)
        self.assertEqual(self.post('accruals',{**p,'acquired':3}).status_code,200)
        self.assertEqual(self.post('accruals',p).status_code,200)
        self.assertFalse(self.data()['employees'][0]['balance']['accrual']['manual'])
    def test_acquired_preserves_opening_balance_and_exports(self):
        p=dict(employee=self.eid,year=self.year,asof=date.today().isoformat(),acquired=3,assigned=14,reason='Confirmado')
        self.post('opening-balances',dict(employee=self.eid,year=self.year,cutoff=date.today().isoformat(),remaining=7,reason='Inicial',confirm=True))
        self.assertEqual(self.post('accruals',p).status_code,200)
        b=self.data()['employees'][0]['balance'];self.assertEqual(b['available'],7);self.assertEqual(b['accrual']['acquired'],3)
        book=load_workbook(io.BytesIO(self.c.get('/api/export?year='+str(self.year)).data))
        values=dict(zip([c.value for c in book.active[1]],[c.value for c in book.active[2]]))
        self.assertEqual(values['Adquiridos al cómputo'],3);self.assertEqual(values['Disponibles'],7)
    def test_acquired_backup_restoration_and_legacy_schema(self):
        import sqlite3
        from pathlib import Path
        p=dict(employee=self.eid,year=self.year,asof=date.today().isoformat(),acquired=3,reason='Confirmado')
        self.post('accruals',p);backup=self.c.get('/api/backup').data
        self.post('accruals',{**p,'acquired':8})
        r=self.c.post('/api/restore',data={'file':(io.BytesIO(backup),'backup.sqlite'),'confirm':'RESTAURAR','password':'contraseña-segura-123'},headers={'X-CSRF-Token':self.csrf})
        self.assertEqual(r.status_code,200)
        self.c.get('/')
        with self.c.session_transaction() as sess:self.csrf=sess['csrf']
        self.post('login',dict(username='admin',password='contraseña-segura-123'))
        self.assertEqual(self.data()['employees'][0]['balance']['accrual']['acquired'],3)
        with sqlite3.connect(Path(self.tmp.name)/'rrhh.sqlite') as con:
            con.execute('DROP TABLE accruals');con.commit();legacy=con.serialize()
        create_app(self.tmp.name)
        r=self.c.post('/api/restore',data={'file':(io.BytesIO(legacy),'legacy.sqlite'),'confirm':'RESTAURAR','password':'contraseña-segura-123'},headers={'X-CSRF-Token':self.csrf})
        self.assertEqual(r.status_code,200)

    def test_monthly_indicators_include_all_licenses_and_unique_people(self):
        first=date.today().replace(day=1)
        for i,kind in enumerate(['Vacaciones','Estudio','Trámites personales']):
            day=(first+timedelta(days=i)).isoformat()
            self.assertEqual(self.absence(type=kind,start=day,end=day).status_code,200)
        stats=self.data()['stats'];self.assertEqual(stats['current'],1)
        self.assertEqual(stats['current_detail'],dict(total=1,vacations=1,leaves=1))
        next_month=(first.replace(day=28)+timedelta(days=4)).replace(day=1)
        r=self.absence(type='Estudio',start=next_month.isoformat(),end=next_month.isoformat())
        self.assertEqual(r.status_code,200);self.assertEqual(self.data()['stats']['next_detail'],dict(total=1,vacations=0,leaves=1))
    def test_license_days_by_calendar_year_do_not_consume_vacation_balance(self):
        before=self.data()['employees'][0]['balance']['available']
        self.assertEqual(self.absence(type='Estudio',year=2024,start='2025-12-29',end='2026-01-03').status_code,200)
        self.assertEqual(self.absence(type='Trámites personales',year=2025,start='2025-08-01',end='2025-08-02').status_code,200)
        self.assertEqual(self.absence(type='Estudio',start='2025-09-01',end='2025-09-03',state='Solicitadas').status_code,200)
        self.assertEqual(self.absence(type='Estudio',start='2025-10-01',end='2025-10-04',state='Canceladas').status_code,200)
        self.assertEqual(self.absence(type='Estudio',start='2025-11-01',end='2025-11-04',state='Rechazadas').status_code,200)
        e=self.c.get('/api/data?year=2025').json['employees'][0]
        self.assertEqual(e['leaves']['total'],5);self.assertEqual(e['leaves']['pending'],3)
        self.assertEqual(e['leaves']['by_type']['Estudio']['total'],3)
        self.assertEqual(e['leaves']['by_type']['Trámites personales']['total'],2)
        self.assertEqual(self.c.get('/api/data?year=2026').json['employees'][0]['leaves']['total'],3)
        self.assertEqual(self.data()['employees'][0]['balance']['available'],before)
        book=load_workbook(io.BytesIO(self.c.get('/api/export?year=2025').data));row=dict(zip([c.value for c in book.active[1]],[c.value for c in book.active[2]]))
        self.assertEqual(row['Días licencia año'],5)
    def test_license_pending_and_cancelled_do_not_inflate_monthly_counts(self):
        first=date.today().replace(day=1).isoformat()
        a=self.absence(type='Estudio',start=first,end=first,state='Solicitadas');self.assertEqual(a.status_code,200)
        self.assertEqual(self.data()['stats']['current'],0)
        a=self.absence(id=a.json['id'],type='Estudio',start=first,end=first);self.assertEqual(a.status_code,200)
        self.assertEqual(self.data()['stats']['current'],1)
        self.assertEqual(self.absence(id=a.json['id'],type='Estudio',start=first,end=first,state='Canceladas').status_code,200)
        self.assertEqual(self.data()['stats']['current'],0)
    def test_repeatable_excel_skip_preserves_existing_employee(self):
        wb=Workbook();ws=wb.active;ws.append(['code','first','last','sector','position','hired'])
        ws.append(['E1','No reemplazar','Otro','Otro','Otro','2020-01-01']);ws.append(['E2','Ficticia','Nueva','Ventas','Analista','2020-01-01'])
        out=io.BytesIO();wb.save(out);blob=out.getvalue()
        for expected in [(1,1),(0,2)]:
            r=self.c.post('/api/import',data={'file':(io.BytesIO(blob),'nomina.xlsx'),'skip_existing':'1'},headers={'X-CSRF-Token':self.csrf})
            self.assertEqual(r.status_code,200);self.assertEqual((r.json['count'],r.json['skipped']),expected)
        employees=self.data()['employees'];self.assertEqual(len(employees),2)
        original=next(e for e in employees if e['code']=='E1');self.assertEqual(original['first'],'Ana');self.assertEqual(original['sector'],'Ventas')
        from pathlib import Path
        path=Path(self.tmp.name)/'roster.xlsx';path.write_bytes(blob)
        result=self.app.test_cli_runner().invoke(args=['import-roster',str(path),'--skip-existing'])
        self.assertEqual(result.exit_code,0,result.output);self.assertIn('existentes omitidos: 2',result.output)

if __name__=='__main__':unittest.main()
