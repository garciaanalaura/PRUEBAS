"""Consistent SQLite backups and a portable single-instance maintenance lock."""
from contextlib import contextmanager, closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import uuid

@contextmanager
def process_lock(directory):
    directory=Path(directory);directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    path=directory/'corevia.service.lock'
    handle=open(path,'a+b')
    if path.stat().st_size==0:
        handle.write(b'0');handle.flush()
    handle.seek(0)
    try:
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError('Corevia está en ejecución u otra operación está usando la base. Detené el servicio antes de continuar.') from exc
        yield
    finally:
        # Closing releases the OS lock. Keep the inode; deleting it permits races.
        handle.close()


@contextmanager
def readonly(path):
    connection=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True,timeout=30)
    try:yield connection
    finally:connection.close()


def backup_database(source, directory, prefix='corevia'):
    """SQLite online backup API, independent connection, no copying an active DB file."""
    directory=Path(directory);directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    target=directory/f'{prefix}-{stamp}-{uuid.uuid4().hex[:12]}.sqlite'
    temporary=target.with_suffix('.partial')
    try:
        with readonly(source) as src, closing(sqlite3.connect(temporary)) as dst:
            src.backup(dst,pages=256,sleep=0.05)
            dst.execute('PRAGMA journal_mode=DELETE')
            if dst.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                raise ValueError('La copia no pasó la verificación de integridad.')
        temporary.chmod(0o600);temporary.rename(target)
        digest=hashlib.sha256(target.read_bytes()).hexdigest()
        manifest=target.with_suffix('.json')
        manifest.write_text(json.dumps(dict(file=target.name,sha256=digest,created_utc=stamp),indent=2),encoding='utf-8')
        manifest.chmod(0o600)
        return target
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
