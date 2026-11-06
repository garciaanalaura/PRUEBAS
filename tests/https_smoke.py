"""Real TLS + loopback reverse proxy smoke test. All data/certificates are temporary.
Run with the project's Python. Requires openssl; never disables TLS verification.
"""
from datetime import date, timedelta
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import http.cookiejar
import json
import os
from pathlib import Path
import re
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parent.parent
PASSWORD='password-ficticio-para-prueba-1234'


def main():
    with tempfile.TemporaryDirectory(prefix='corevia-tls-') as tmp:
        root=Path(tmp);data=root/'data'
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        config=root/'server.toml'
        config.write_text(f'''environment="production"
data_dir="{data.as_posix()}"
backup_dir="{(root/'backups').as_posix()}"
log_dir="{(root/'logs').as_posix()}"
allowed_hosts=["localhost"]
allowed_networks=["127.0.0.1/32"]
''')
        env={**os.environ,'COREVIA_CONFIG':str(config),'COREVIA_ENV':'production','RRHH_DATA':str(data),'RRHH_HOST':'127.0.0.1','RRHH_PORT':str(port)}
        bootstrap=subprocess.run([sys.executable,'-m','flask','--app','app:create_app','create-admin','admin-prueba'],cwd=ROOT,env=env,input=PASSWORD+'\n'+PASSWORD+'\n',text=True,capture_output=True)
        assert bootstrap.returncode==0,bootstrap.stderr
        server=subprocess.Popen([sys.executable,'run_server.py'],cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        proxy=None;thread=None
        try:
            for _ in range(100):
                if server.poll() is not None:raise AssertionError('No inició Waitress: '+server.stderr.read().decode())
                try:
                    c=http.client.HTTPConnection('127.0.0.1',port,timeout=1);c.request('GET','/healthz');r=c.getresponse();r.read();c.close()
                    if r.status==200:break
                except OSError:pass
                time.sleep(.1)
            else:raise AssertionError('Waitress no quedó disponible.')
            cert=root/'cert.pem';key=root/'key.pem'
            subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(key),'-out',str(cert),'-days','1','-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost,IP:127.0.0.1'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            class Proxy(BaseHTTPRequestHandler):
                def forward(self):
                    body=self.rfile.read(int(self.headers.get('Content-Length','0')))
                    headers={k:v for k,v in self.headers.items() if k.lower() in ('cookie','content-type','x-csrf-token','if-match')}
                    headers.update({'Host':'localhost','X-Forwarded-Proto':'https','X-Forwarded-For':self.client_address[0]})
                    upstream=http.client.HTTPConnection('127.0.0.1',port,timeout=30)
                    upstream.request(self.command,self.path,body=body,headers=headers)
                    response=upstream.getresponse();payload=response.read()
                    self.send_response(response.status)
                    for name,value in response.getheaders():
                        if name.lower() not in ('connection','transfer-encoding','content-length','server','date'):self.send_header(name,value)
                    self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload);upstream.close()
                do_GET=forward;do_POST=forward
                def log_message(self,*_):pass
            proxy=ThreadingHTTPServer(('127.0.0.1',0),Proxy)
            tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.load_cert_chain(cert,key)
            proxy.socket=tls.wrap_socket(proxy.socket,server_side=True)
            thread=threading.Thread(target=proxy.serve_forever,daemon=True);thread.start()
            base=f'https://localhost:{proxy.server_port}'
            # Test certificate explicitly trusted, hostname validation stays enabled.
            trust=ssl.create_default_context(cafile=str(cert))
            def client(username):
                opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),urllib.request.HTTPSHandler(context=trust))
                html=opener.open(base+'/').read().decode();token=re.search(r'name="csrf" content="([^"]+)"',html).group(1)
                status,_,_=request(opener,'/api/login',{'username':username,'password':PASSWORD},token)
                assert status==200
                return opener,token
            def request(opener,path,body=None,token=None,revision=None):
                headers={}
                if body is not None:headers.update({'Content-Type':'application/json','X-CSRF-Token':token})
                if revision is not None:headers['If-Match']=str(revision)
                req=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
                try:response=opener.open(req,timeout=30)
                except urllib.error.HTTPError as error:response=error
                raw=response.read()
                content=json.loads(raw) if 'application/json' in response.headers.get('Content-Type','') else raw
                return response.status,content,response.headers
            admin,token=client('admin-prueba')
            _,info,_=request(admin,'/api/data');revision=info['revision']
            status,result,headers=request(admin,'/api/employees',dict(code='TLS-1',first='Persona',last='Ficticia',sector='Pruebas',position='Analista',hired='2020-01-01'),token,revision);assert status==200,result
            eid=result['id'];revision=int(headers['X-Corevia-Revision'])
            status,result,headers=request(admin,'/api/users',dict(username='gerencia-prueba',password=PASSWORD,role='lectura'),token,revision);assert status==200,result
            revision=int(headers['X-Corevia-Revision']);manager,manager_token=client('gerencia-prueba')
            status,info,_=request(manager,'/api/data');assert status==200 and len(info['employees'])==1
            assert request(manager,'/api/employees',dict(code='DENIED'),manager_token,revision)[0]==403
            start=date.today()+timedelta(days=30)
            status,result,headers=request(admin,'/api/absences',dict(employee=eid,year=date.today().year,type='Vacaciones',start=start.isoformat(),end=(start+timedelta(days=3)).isoformat(),state='Aprobadas',requested=date.today().isoformat(),approved=date.today().isoformat(),approver='Prueba'),token,revision);assert status==200,result
            _,info,_=request(manager,'/api/data');assert info['employees'][0]['balance']['reserved']==4
            _,backup,_=request(admin,'/api/backup');source=root/'snapshot.sqlite';source.write_bytes(backup)
            blocked=subprocess.run([sys.executable,'manage.py','restore',str(source),'--confirm','RESTAURAR'],cwd=ROOT,env=env,capture_output=True,text=True)
            assert blocked.returncode!=0 and 'ejecución' in blocked.stderr,blocked.stderr
            assert request(admin,'/api/restore',{},token)[0]==403
            print('OK: HTTPS con certificado verificado, proxy real de loopback, RRHH/Gerencia, datos compartidos, cuatro días reservados y restauración bloqueada mientras el servicio funciona.')
        finally:
            if proxy:proxy.shutdown();proxy.server_close()
            if thread:thread.join(timeout=5)
            if server.poll() is None:server.terminate()
            server.wait(timeout=15)
            assert server.returncode==0,'El servicio no terminó correctamente.'

if __name__=='__main__':main()
