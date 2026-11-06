"""Configuration without credentials in source control; production fails closed."""
from dataclasses import dataclass
import ipaddress
import os
from pathlib import Path
import tomllib

PROJECT = Path(__file__).resolve().parent.parent

@dataclass(frozen=True)
class Settings:
    environment: str
    data_dir: Path
    backup_dir: Path
    log_dir: Path
    host: str
    port: int
    threads: int
    allowed_hosts: tuple[str, ...]
    allowed_networks: tuple
    idle_seconds: int
    absolute_seconds: int
    refresh_seconds: int
    secure_cookie: bool

    @property
    def production(self):
        return self.environment == 'production'


def load_settings(data_dir=None):
    values = {}
    filename = os.environ.get('COREVIA_CONFIG')
    if filename:
        with open(filename, 'rb') as source:
            values = tomllib.load(source)
    def value(name, default, env=None):
        return os.environ.get(env or 'COREVIA_' + name.upper(), values.get(name, default))
    environment = str(value('environment', 'local', 'COREVIA_ENV'))
    if environment not in ('local', 'production'):
        raise ValueError('COREVIA_ENV debe ser local o production.')
    production = environment == 'production'
    root = Path(data_dir or value('data_dir', PROJECT / 'data', 'RRHH_DATA')).expanduser()
    if production and (not root.is_absolute() or root.resolve().is_relative_to(PROJECT)):
        raise ValueError('Producción requiere RRHH_DATA/data_dir absoluto y fuera de la carpeta del código.')
    if production and str(root).startswith(('\\\\', '//')):
        raise ValueError('SQLite debe estar en disco local del servidor, no en una ruta UNC compartida.')
    root = root.resolve()
    backups = Path(value('backup_dir', root / 'backups')).expanduser().resolve()
    logs = Path(value('log_dir', root / 'logs')).expanduser().resolve()
    host = str(value('host', '127.0.0.1', 'RRHH_HOST'))
    if host not in ('127.0.0.1', '::1', 'localhost'):
        raise ValueError('Corevia escucha en loopback. Usá un proxy HTTPS interno en el mismo servidor.')
    def number(name, default, low, high, env=None):
        result = int(value(name, default, env))
        if not low <= result <= high:
            raise ValueError(f'Valor fuera de rango: {name}.')
        return result
    raw_hosts = value('allowed_hosts', ['localhost', '127.0.0.1', '::1'] if not production else [])
    hosts = tuple(x.strip() for x in raw_hosts.split(',') if x.strip()) if isinstance(raw_hosts, str) else tuple(raw_hosts)
    if any(not isinstance(h,str) for h in hosts):raise ValueError('allowed_hosts debe contener nombres de servidor.')
    hosts=tuple(h.strip().lower().rstrip('.') for h in hosts)
    raw_networks = value('allowed_networks', [])
    networks = raw_networks.split(',') if isinstance(raw_networks, str) else raw_networks
    networks = tuple(ipaddress.ip_network(str(x).strip(), strict=True) for x in networks if str(x).strip())
    if production:
        if not hosts or any(not h or h.startswith('.') or '*' in h or '://' in h or '/' in h for h in hosts):
            raise ValueError('Producción requiere allowed_hosts con nombres internos exactos, sin comodines.')
        if not networks or any(n.prefixlen == 0 for n in networks):
            raise ValueError('Producción requiere allowed_networks con las subredes internas autorizadas.')
        if os.name!='nt' and any(p.exists() and p.stat().st_mode & 0o007 for p in (root,backups,logs)):
            raise ValueError('Datos, copias y logs deben estar en directorios privados, sin acceso para otros usuarios del sistema.')
        if any(p.is_relative_to(PROJECT) for p in (backups, logs)):
            raise ValueError('Las copias y logs de producción deben quedar fuera del código.')
    return Settings(environment, root, backups, logs, host,
        number('port',8080,1024,65535,'RRHH_PORT'), number('threads',4,1,16), hosts, networks,
        number('idle_seconds',1800 if production else 28800,60,28800),
        number('absolute_seconds',28800,300,86400), number('refresh_seconds',30,10,300),
        production or os.environ.get('RRHH_HTTPS') == '1')
