"""Entrypoint shared by local launcher, systemd and the Windows service wrapper."""
import signal
from waitress import create_server
from corevia.config import load_settings
from corevia.storage import process_lock


def _run():
    settings=load_settings()
    from app import create_app
    with process_lock(settings.data_dir):
        app=create_app()
        server=create_server(app,host=settings.host,port=settings.port,threads=settings.threads,
            ident='Corevia',max_request_body_size=10*1024*1024,channel_timeout=60,
            clear_untrusted_proxy_headers=False)
        # Only the loopback proxy is accepted by Flask in production. ProxyFix handles
        # exactly one forwarding hop, never X-Forwarded-Host or additional proxies.
        def stop(_signal,_frame):raise KeyboardInterrupt
        signal.signal(signal.SIGTERM,stop)
        print(f'Corevia ({settings.environment}) en {settings.host}:{settings.port}.',flush=True)
        try:server.run()
        except KeyboardInterrupt:pass
        finally:server.close()


def main():
    try:_run()
    except (ValueError,RuntimeError,OSError) as exc:
        raise SystemExit(f'Corevia no inició: {exc}') from None


if __name__=='__main__':main()
