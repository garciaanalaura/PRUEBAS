"""Offline migration/restoration and online consistent backups. Never deploys."""
from pathlib import Path
from contextlib import closing
import sqlite3
import click
from app import prepare_candidate, create_app
from corevia.config import load_settings
from corevia.storage import backup_database, process_lock, readonly
from corevia.security import SecurityStore

@click.group()
def cli():
    """Herramientas de Sistemas para Corevia."""

@cli.command('backup')
@click.option('--output',type=click.Path(file_okay=False,path_type=Path))
def backup(output):
    """Copia consistente verificable, incluso con el servicio en uso."""
    settings=load_settings()
    try:
        path=backup_database(settings.data_dir/'rrhh.sqlite',output or settings.backup_dir)
    except (sqlite3.Error,ValueError,OSError) as exc:
        raise click.ClickException('No se pudo crear o verificar la copia. Revisá permisos, espacio y la base de origen.') from exc
    click.echo(f'Copia verificada: {path}')


def install_backup(source,replace=False):
    settings=load_settings();target=settings.data_dir/'rrhh.sqlite'
    with process_lock(settings.data_dir):
        if target.exists() and not replace:
            raise click.ClickException('Ya existe una base. La migración no la sobrescribe. Para recuperar, usá restore con confirmación.')
        if source.resolve()==target.resolve():raise click.ClickException('El origen y el destino deben ser distintos.')
        candidate=sqlite3.connect(':memory:')
        try:
            with readonly(source) as src:src.backup(candidate)
            prepare_candidate(candidate)
            users=candidate.execute('SELECT count(*) FROM users').fetchone()[0]
            admins=candidate.execute("SELECT count(*) FROM users WHERE active=1 AND role='admin'").fetchone()[0]
            if users and not admins:raise click.ClickException('La copia tiene usuarios pero no un administrador activo.')
            if target.exists():backup_database(target,settings.backup_dir,'antes-restauracion')
            with closing(sqlite3.connect(target)) as dst:
                candidate.backup(dst)
                dst.execute("UPDATE app_meta SET value=CAST(value AS INTEGER)+1 WHERE key='revision'")
                dst.commit()
            target.chmod(0o600)
            store=SecurityStore(settings.data_dir/'security.sqlite',settings.idle_seconds,settings.absolute_seconds)
            store.revoke()
            counts={t:candidate.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in ('employees','absences','balances','opening_balances','accruals','users')}
        finally:candidate.close()
    return counts

@cli.command('migrate')
@click.argument('source',type=click.Path(exists=True,dir_okay=False,path_type=Path))
def migrate(source):
    """Instalar copia local en un destino vacío, preservando el original."""
    try:counts=install_backup(source)
    except (sqlite3.Error,ValueError,OSError,RuntimeError) as exc:raise click.ClickException(str(exc)) from exc
    click.echo('Migración verificada. Conteos: '+str(counts))

@cli.command('restore')
@click.argument('source',type=click.Path(exists=True,dir_okay=False,path_type=Path))
@click.option('--confirm',required=True,type=click.Choice(['RESTAURAR']))
def restore(source,confirm):
    """Requiere servicio detenido, preserva una copia previa y revoca sesiones."""
    try:counts=install_backup(source,replace=True)
    except (sqlite3.Error,ValueError,OSError,RuntimeError) as exc:raise click.ClickException(str(exc)) from exc
    click.echo('Restauración verificada. Conteos: '+str(counts))

@cli.command('check')
def check():
    """Verificar integridad/referencias sin mostrar información personal."""
    settings=load_settings()
    try:
        with readonly(settings.data_dir/'rrhh.sqlite') as db:
            if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchone():
                raise click.ClickException('La base requiere revisión de integridad o referencias.')
    except sqlite3.Error as exc:raise click.ClickException('No se pudo verificar la base.') from exc
    click.echo('Integridad y referencias: OK.')

if __name__=='__main__':cli()
