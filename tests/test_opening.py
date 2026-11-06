"""Regression tests for imported remaining balances and historical vacation records."""
import io
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from openpyxl import load_workbook
from app import create_app, SCHEMA

class OpeningTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.app=create_app(self.tmp.name);self.app.testing=True
        self.c=self.app.test_client();self.login(setup=True)
        self.year=2025
        self.eid=self.post('employees',dict(code='T1',first='Ana',last='Prueba',sector='RRHH',position='Analista',hired='2010-01-01')).json['id']
    def tearDown(self):self.tmp.cleanup()
    def login(self,setup=False,username='admin'):
        self.c.get('/')
        with self.c.session_transaction() as s:self.csrf=s['csrf']
        p=dict(username=username,password='prueba-segura-1234')
        if setup:self.assertEqual(self.post('setup',p).status_code,200)
        self.assertEqual(self.post('login',p).status_code,200)
    def post(self,path,p):return self.c.post('/api/'+path,json=p,headers={'X-CSRF-Token':self.csrf})
    def balance(self,year=None):return self.c.get('/api/data?year='+str(year or self.year)).json['employees'][0]['balance']
    def opening(self,**kw):
        p=dict(employee=self.eid,year=self.year,cutoff='2025-10-31',remaining=7,reason='Saldo real validado',confirm=True);p.update(kw)
        return self.post('opening-balances',p)
    def vacation(self,**kw):
        p=dict(employee=self.eid,year=self.year,type='Vacaciones',start='2025-08-01',end='2025-08-07',state='Disfrutadas',requested='2025-08-01',historical=True);p.update(kw)
        return self.post('absences',p)
    def test_history_never_double_deducts_and_is_editable(self):
        self.assertEqual(self.opening().status_code,200)
        a=self.vacation();self.assertEqual(a.status_code,200)
        b=self.balance();self.assertEqual((b['used'],b['included_used'],b['deducted_used'],b['available']),(7,7,0,7))
        self.assertEqual(self.vacation(id=a.json['id'],end='2025-08-10').status_code,200)
        self.assertEqual(self.balance()['available'],7)
        self.assertEqual(self.vacation(id=a.json['id'],end='2025-08-10',state='Canceladas',historical=False).status_code,200)
        self.assertEqual(self.balance()['available'],7)
        self.assertEqual(self.balance()['used'],0)
    def test_after_cutoff_and_straddling_dates_are_counted_once(self):
        self.opening()
        a=self.vacation(start='2025-10-29',end='2025-11-03');self.assertEqual(a.status_code,200)
        self.assertEqual(self.balance()['available'],4)
        b=self.balance();self.assertEqual((b['used'],b['included_used'],b['deducted_used']),(6,3,3))
        # Editing must credit only the old charged days when validating available balance.
        r=self.vacation(id=a.json['id'],start='2025-10-29',end='2025-11-08')
        self.assertEqual(r.status_code,409)
        self.assertEqual(self.balance()['available'],4)
        self.assertEqual(self.vacation(id=a.json['id'],start='2025-10-29',end='2025-11-04').status_code,200)
        self.assertEqual(self.balance()['available'],3)
    def test_zero_balance_future_reservations_and_licenses(self):
        self.opening(remaining=0)
        self.assertEqual(self.vacation().status_code,200)
        self.assertEqual(self.balance()['available'],0)
        future=(date.today()+timedelta(days=20)).isoformat()
        r=self.vacation(start=future,end=future,state='Aprobadas',historical=False,approved=date.today().isoformat(),approver='RRHH')
        self.assertEqual(r.status_code,409)
        r=self.vacation(start=future,end=future,state='Aprobadas',historical=False,approved=date.today().isoformat(),approver='RRHH',confirm=True)
        self.assertEqual(r.status_code,200);self.assertEqual(self.balance()['reserved'],1);self.assertEqual(self.balance()['available'],-1)
        self.assertEqual(self.vacation(type='Estudio',start='2025-11-11',end='2025-11-15',historical=False).status_code,200)
        self.assertEqual(self.balance()['available'],-1)
    def test_years_manual_assignment_switch_and_audit(self):
        self.post('balances',dict(employee=self.eid,year=2025,assigned=14,adjustment=0,reason='Total real'))
        a=self.vacation();self.assertEqual(a.status_code,200);self.assertEqual(self.balance()['available'],7)
        self.opening();self.opening(year=2024,remaining=3)
        self.assertEqual(self.balance(2024)['available'],3);self.assertEqual(self.balance(2025)['available'],7)
        # Annual edits do not silently erase an active imported remaining balance.
        self.post('balances',dict(employee=self.eid,year=2025,assigned=20,adjustment=1,reason='Nuevo total'))
        self.assertEqual(self.balance()['available'],7)
        self.assertEqual(self.opening(clear=True,reason='Volver a total anual').status_code,200)
        self.assertEqual(self.balance()['available'],14)
        self.assertEqual(self.balance(2024)['available'],3)
        logs=self.c.get('/api/audit').json;self.assertTrue(any(l['action']=='Actualizar saldo inicial' and 'Saldo real validado' in l['detail'] for l in logs))
    def test_snapshot_before_or_after_history_same_result_and_persistence(self):
        self.vacation();self.opening();self.assertEqual(self.balance()['available'],7)
        self.opening(remaining=9);self.assertEqual(self.balance()['available'],9)
        self.c=create_app(self.tmp.name).test_client();self.login()
        self.assertEqual(self.balance()['available'],9)
    def test_validations_readonly_and_overlap(self):
        for kw in [dict(remaining=-1),dict(remaining='NaN'),dict(remaining='Infinity'),dict(cutoff='2000-01-01'),dict(cutoff=(date.today()+timedelta(days=1)).isoformat()),dict(year=0),dict(confirm=False),dict(reason=''),dict(employee=99999)]:
            self.assertEqual(self.opening(**kw).status_code,400,kw)
        self.opening();self.vacation();self.assertEqual(self.vacation().status_code,400)
        self.assertEqual(self.vacation(start=(date.today()+timedelta(days=2)).isoformat(),end=(date.today()+timedelta(days=2)).isoformat()).status_code,400)
        self.post('users',dict(username='gerencia',password='prueba-segura-1234',role='lectura'))
        self.post('logout',{});self.login(username='gerencia');self.assertEqual(self.opening().status_code,403)
        self.assertEqual(self.balance()['opening']['remaining'],7)
    def test_export_backup_restore_and_demo_cleanup(self):
        self.opening();self.vacation()
        book=load_workbook(io.BytesIO(self.c.get('/api/export?year=2025').data))
        row=dict(zip([c.value for c in book.active[1]],[c.value for c in book.active[2]]))
        self.assertEqual(row['Disponibles'],7);self.assertEqual(row['Saldo inicial real'],7);self.assertEqual(row['Utilizados incluidos en saldo inicial'],7)
        backup=self.c.get('/api/backup').data
        self.opening(remaining=2)
        r=self.c.post('/api/restore',data={'file':(io.BytesIO(backup),'rrhh.sqlite'),'confirm':'RESTAURAR','password':'prueba-segura-1234'},headers={'X-CSRF-Token':self.csrf})
        self.assertEqual(r.status_code,200);self.login();self.assertEqual(self.balance()['available'],7)
        self.post('demo',{});demo=next(e for e in self.c.get('/api/data').json['employees'] if e['demo'])
        self.opening(employee=demo['id'])
        self.assertEqual(self.post('demo',dict(delete=True,confirm='ELIMINAR DEMO')).status_code,200)
        self.assertEqual(self.balance()['available'],7)
    def test_legacy_database_and_backup_migration_preserve_old_calculation(self):
        self.vacation();before=self.balance()['available']
        # Reproduce a database created before the new table existed.
        path=Path(self.tmp.name)/'rrhh.sqlite'
        with sqlite3.connect(path) as con:
            con.execute('DROP TABLE opening_balances');con.commit();legacy=con.serialize()
        self.app=create_app(self.tmp.name);self.c=self.app.test_client();self.login()
        self.assertEqual(self.balance()['available'],before)
        self.opening()
        r=self.c.post('/api/restore',data={'file':(io.BytesIO(legacy),'legacy.sqlite'),'confirm':'RESTAURAR','password':'prueba-segura-1234'},headers={'X-CSRF-Token':self.csrf})
        self.assertEqual(r.status_code,200);self.login()
        self.assertEqual(self.balance()['available'],before);self.assertIsNone(self.balance()['opening'])
        self.assertEqual(self.balance()['used'],7)

if __name__=='__main__':unittest.main()
