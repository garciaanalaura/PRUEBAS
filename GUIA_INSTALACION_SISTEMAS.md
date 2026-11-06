# Corevia — guía de instalación para Sistemas

Preparación para Personal Collect S.A. Esta entrega contiene código y plantillas; **no instala servicios, abre puertos ni despliega en la red corporativa**. Los nombres `corevia.interno.example` y las IP `10.0.0.x` son ejemplos reservados, no destinos configurados.

## 1. Arquitectura y alcance

```text
PC RR. HH. ─┐
             ├── HTTPS / red interna ── IIS o Nginx ── 127.0.0.1:8080 / Waitress
PC Gerencia ┘                                                  │
                                                  SQLite en disco LOCAL
                                                  del servidor autorizado
```

Un único equipo de servidor o VM, un único proceso Corevia con cuatro hilos inicialmente, una única base central. Las computadoras cliente solo necesitan navegador: **no ejecutan Python ni guardan una copia de la base**. El servidor debe permanecer encendido; no depende de una sesión interactiva de RR. HH.

Se conserva SQLite para evitar una migración innecesaria de datos y porque admite lectores simultáneos y escrituras breves serializadas mediante WAL. No usar SQLite sobre SMB, NFS, OneDrive ni carpetas compartidas/sincronizadas. No iniciar varias instancias, varios workers o varias réplicas contra la misma base. Se incluye bloqueo de instancia y mantenimiento.

Las pantallas consultan cambios cada 30 segundos, al volver al navegador y después de guardar. No son notificaciones push. Mientras hay un formulario abierto no se refresca su contenido. Cada escritura lleva una revisión de la base: si otro usuario cambió información, el servidor responde 409 y conserva el formulario para revisar los cambios, en vez de sobrescribirlos. La revisión es global: puede pedir revisión incluso si la otra operación afectó a otra persona.

El modo central mantiene empleados, calendario, vacaciones, licencias, saldos por año, ajustes, saldos iniciales e historial, Excel, roles y auditoría. Vacaciones y licencias siguen teniendo cómputos separados. Gerencia puede consultar y exportar; solo Administración modifica datos laborales, administra cuentas, descarga respaldos y consulta auditoría. Cada usuario puede cambiar su propia contraseña.

## 2. Decisiones que Sistemas debe confirmar

Antes de instalar, confirmar:

| Decisión | Alternativas / impacto |
|---|---|
| Servidor | Windows Server con servicio WinSW e IIS/ARR, o Linux con systemd y Nginx. No se presupone cuál existe. |
| Capacidad | Cantidad de usuarios simultáneos, nómina, tamaño histórico y frecuencia de importaciones. Validar un piloto con la carga esperada. |
| DNS y HTTPS | Nombre interno definitivo, IP privada, certificados de la PKI corporativa y su confianza en las PC. |
| Red autorizada | Subredes, segmentación y acceso remoto por los mecanismos corporativos ya autorizados. Sin NAT ni puertos públicos. |
| Cuentas | Cuenta de servicio restringida, administradores de Corevia y usuarios individuales de consulta. No se implementa SSO/Active Directory en esta entrega. |
| Respaldo | Destino autorizado, cifrado, retención, horario, objetivo de pérdida máxima (RPO), tiempo de recuperación (RTO) y responsable de probar restauraciones. |
| Datos de origen | Identificar cuál base local contiene el historial definitivo. No combinar ni reemplazar bases basándose solo en sus fechas de archivo. |
| Evolución | Si se requieren muchas escrituras simultáneas, alta disponibilidad o varias réplicas, planificar PostgreSQL y su migración en una tarea específica. |

## 3. Requisitos

- Sistema operativo mantenido, Linux con systemd o Windows Server compatible con Python y el proxy elegido.
- Python **3.12 recomendado**, con venv y pip; probado en Linux/Python 3.12. No se ejecutó Windows Server durante esta preparación.
- Punto inicial orientativo para un piloto pequeño: 2 vCPU, 4 GB RAM y 10 GB libres en SSD local, más espacio calculado para respaldos y retención. No equivale a una prueba de capacidad para una nómina o carga determinada.
- Edge/Chrome/Firefox actualizado en las PC. HTTPS válido y confianza de la CA interna; no desactivar la verificación de certificados.
- Hora del servidor sincronizada y zona local **America/Argentina/Buenos_Aires** o equivalente de Windows. Los días de vacaciones/licencias se calculan con la fecha del servidor; los vencimientos de sesión usan tiempo UTC.
- Proxy interno en el mismo servidor; backend solo en loopback. Firewall y ACL bajo responsabilidad de Sistemas, con autorización. No exponer 8080 a las PC ni a Internet.
- Descargas iniciales de Python, dependencias y componentes del sistema desde sus fuentes oficiales, mediante el procedimiento corporativo. No se necesita Internet para el uso normal una vez instalados.

Dependencias Python fijadas en `requirements-lock.txt`. Flask se actualizó a 3.1.3 para corregir el aviso GHSA-68rp-wp8r-4726 sobre caché de sesiones; los avisos publicados en PyPI se revisaron para las versiones fijadas. Esa consulta no sustituye una auditoría independiente ni el seguimiento de futuras actualizaciones. El proyecto no requiere Node, Playwright, OpenSSL ni un compilador para el uso cotidiano. Playwright/Chromium y OpenSSL se usan solo en las pruebas opcionales de desarrollo.

## 4. Separar código, configuración y datos

Ejemplo Linux:

```text
/opt/corevia/releases/<commit>/     código de una versión
/opt/corevia/current                enlace a la versión aprobada
/opt/corevia/venv/                  entorno Python
/etc/corevia/corevia.toml           configuración privada
/var/lib/corevia/                   rrhh.sqlite, session.key, security.sqlite, lock
/var/backups/corevia/               copias verificadas y manifiestos
/var/log/corevia/                   registros operativos
```

Ejemplo Windows:

```text
C:\Corevia\releases\<commit>\       código de una versión
C:\Corevia\current\                 versión aprobada (ruta o junction administrada)
C:\Corevia\venv\                    entorno Python
C:\ProgramData\Corevia\config\corevia.toml
C:\ProgramData\Corevia\data\        datos, claves y bloqueo
C:\ProgramData\Corevia\backups\
C:\ProgramData\Corevia\logs\
```

En Linux, los comandos que crean o restauran bases, cuentas, copias o claves deben ejecutarse con la cuenta `corevia` (por ejemplo `sudo -u corevia env COREVIA_CONFIG=... <python> ...`), no como root: un archivo creado por root con modo 0600 impediría iniciar el servicio. En Windows aplicar las ACL heredables previstas también a los archivos creados durante la migración.

La aplicación exige datos y logs de producción **fuera de la carpeta del código**. No guardar claves, bases, Excel de empleados ni certificados privados en Git. La clave `session.key` se genera en el servidor, no se distribuye con el proyecto. `security.sqlite` contiene sesiones revocables y límites de acceso; no es una fuente de datos laborales ni se migra desde una PC.

Usar cuenta de servicio sin permisos administrativos. Código de solo lectura para esa cuenta; escritura únicamente en datos, copias y logs. En Linux usar directorios privados (por ejemplo 0700), archivos 0600 y `UMask=0077`. En Windows configurar ACL NTFS: servicio y administradores autorizados; quitar acceso de usuarios comunes/heredado amplio. `chmod` de Python no sustituye las ACL de Windows. Aplicar BitLocker/LUKS o cifrado de disco y respaldos conforme a la política de la empresa: SQLite no cifra la información por sí misma.

## 5. Configuración de producción

Copiar y completar una de estas plantillas **fuera del checkout**:

- `deployment/linux/corevia.toml.example`
- `deployment/windows/corevia.toml.example`

Establecer `COREVIA_CONFIG` con la ruta del TOML. La plantilla contiene `environment = "production"`. También puede usarse `COREVIA_ENV=production`; las variables de entorno prevalecen sobre el archivo. Revisar que no queden variables heredadas `RRHH_DATA`, `RRHH_HOST`, `RRHH_PORT` ni `COREVIA_*` apuntando a otra instalación.

| Campo TOML | Variable equivalente | Uso |
|---|---|---|
| environment | COREVIA_ENV | `local` o `production` |
| data_dir | RRHH_DATA | Directorio absoluto de datos, externo al código |
| backup_dir | COREVIA_BACKUP_DIR | Directorio privado de copias |
| log_dir | COREVIA_LOG_DIR | Directorio privado de errores |
| host | RRHH_HOST | `127.0.0.1`, `::1` o localhost; nunca 0.0.0.0 |
| port | RRHH_PORT | Puerto de loopback; inicialmente 8080 |
| threads | COREVIA_THREADS | Inicialmente 4; rango 1–16 |
| allowed_hosts | COREVIA_ALLOWED_HOSTS | DNS internos exactos, separados por coma en la variable |
| allowed_networks | COREVIA_ALLOWED_NETWORKS | CIDR autorizados, separados por coma |
| idle_seconds | COREVIA_IDLE_SECONDS | Inactividad de servidor, 1800 s inicialmente |
| absolute_seconds | COREVIA_ABSOLUTE_SECONDS | Duración máxima de sesión, 28800 s |
| refresh_seconds | COREVIA_REFRESH_SECONDS | Consulta automática, 30 s |

Producción falla si faltan DNS/subredes, si se pide un comodín global o si se intenta escuchar públicamente. Activa cookies Secure/HttpOnly/SameSite, exige HTTPS y valida el Host y la IP reenviada. Solo acepta cabeceras reenviadas desde un proxy de loopback y confía en **un** salto. Si la arquitectura exige un proxy en otro equipo o varios saltos, no ampliar esta confianza a ciegas: requiere adaptación y pruebas específicas.

Los sondeos automáticos no prolongan la sesión inactiva. Cambios de contraseña, desactivaciones, cambios de rol y restauraciones revocan sesiones en el servidor. Las contraseñas se almacenan con hash scrypt; no hay contraseñas predeterminadas. La limitación de intentos queda persistida fuera de la base laboral. No se registra el texto de contraseñas ni cuerpos de solicitudes.

## 6. Migración segura de la instalación local

1. Identificar la **base de origen autorizada** y anotar los totales por empleado/año que RR. HH. confirme: nómina, registros de vacaciones/licencias, saldos iniciales y reservas. No usar la base temporal del entorno de desarrollo como reemplazo de la PC.
2. Actualizar y validar una copia de prueba antes de tocar el origen. Reservar una ventana de corte: nadie debe cargar nuevas operaciones en la instalación local después de la copia final.
3. Obtener **Administración → Descargar copia** desde la instalación local. Alternativa de Sistemas con esta versión: `python manage.py backup --output <directorio-seguro>`, usando configuración local con `RRHH_DATA` apuntando al origen. Esta orden usa la API de backup SQLite y funciona con WAL. No copiar solo `rrhh.sqlite` mientras está en uso: puede haber cambios en `-wal`.
4. Conservar una segunda copia fuera del equipo, en destino autorizado. La herramienta CLI genera un manifiesto SHA-256 para verificar el traslado (comparar `sha256sum archivo.sqlite` en Linux o `Get-FileHash archivo.sqlite -Algorithm SHA256` en PowerShell con el manifiesto); esto detecta cambios accidentales, no reemplaza la confianza en el origen.
5. Detener la instalación local al terminar la copia final. Mantener sus archivos originales intactos como contingencia y bloquear nuevas cargas hasta aceptar el servidor central.
6. Preparar el servidor con los directorios, permisos y configuración de producción. **Todavía no iniciar el servicio**. El destino de migración debe estar vacío; no crear una base nueva de prueba allí.
7. Desde el código de la versión elegida y con su configuración de destino:

Linux:

```bash
sudo -u corevia env COREVIA_CONFIG=/etc/corevia/corevia.toml /opt/corevia/venv/bin/python /opt/corevia/current/manage.py migrate /ruta-segura/copia-local.sqlite
sudo -u corevia env COREVIA_CONFIG=/etc/corevia/corevia.toml /opt/corevia/venv/bin/python /opt/corevia/current/manage.py check
```

Windows PowerShell:

```powershell
$env:COREVIA_CONFIG = 'C:\ProgramData\Corevia\config\corevia.toml'
C:\Corevia\venv\Scripts\python.exe C:\Corevia\current\manage.py migrate C:\TransferenciaSegura\copia-local.sqlite
C:\Corevia\venv\Scripts\python.exe C:\Corevia\current\manage.py check
```

8. `migrate` comprueba integridad, referencias y estructura, actualiza el esquema compatible, muestra conteos sin nombres y **rechaza sobrescribir un destino existente**. Preserva el archivo de origen y los hashes de contraseñas. No fusiona dos bases.
9. Si la copia trae usuarios, se conservan. Si es una nómina sin usuarios, crear el primer administrador con `create-admin` según el apartado siguiente. Las sesiones de las PC no se trasladan.
10. Iniciar primero con acceso de Sistemas/RR. HH., comparar los conteos y saldos con el origen y probar Gerencia. Recién después habilitar a los demás usuarios y entregar los accesos directos. Retirar la instalación local del uso diario para evitar dos fuentes de información.

No se ha ejecutado esta migración contra datos de Personal Collect S.A. Las pruebas de migración usaron bases ficticias temporales. La nómina real que se adjuntó anteriormente permanece excluida de Git.

## 7. Usuarios, permisos y recuperación de acceso

El alta web del primer administrador está **deshabilitada en producción**. Crear una cuenta desde consola del servidor, bajo la cuenta autorizada y con `COREVIA_CONFIG` definido:

```bash
# Sustituir la ruta de Python por la de Windows si corresponde.
python -m flask --app app:create_app create-admin usuario_rrhh
```

La contraseña se pide y confirma sin mostrarla. Nunca colocarla en TOML, XML, línea de comandos, historial ni repositorio. `create-admin` no sobrescribe cuentas existentes.

Desde Administración, RR. HH. puede crear cuentas, cambiar roles, desactivar cuentas y restablecer contraseñas. No se puede quitar el último administrador activo. Gerencia no puede modificar datos laborales, usuarios, saldos ni restaurar. El cambio de contraseña propia está disponible junto a Cerrar sesión.

Recuperación por Sistemas, sin editar manualmente hashes:

```bash
python -m flask --app app:create_app reset-password usuario_rrhh
```

La recuperación pide la nueva contraseña, conserva el rol/estado y revoca sesiones. No reactiva automáticamente una cuenta desactivada. Para una desactivación accidental de todas las cuentas por una modificación externa, Sistemas debe investigar y crear un administrador nuevo autorizado; no habilitar usuarios mediante SQL improvisado.

## 8. Instalación como servicio en Linux

Sistemas debe adaptar los comandos a su distribución y realizar los cambios de cuentas, permisos y firewall bajo su autorización. No ejecutar estos pasos sobre un servidor sin revisar rutas existentes.

1. Crear la cuenta `corevia` sin acceso interactivo y los directorios del apartado 4. No usar `root` para ejecutar Corevia. Permitir lectura de código y certificados del proxy solo a las cuentas que correspondan; Corevia no necesita leer la clave TLS del proxy.
2. Descargar una versión/commit aprobado, sin archivos de datos, en `/opt/corevia/releases/<commit>`. Crear o actualizar `current` con el servicio detenido. Mantener una versión anterior para contingencias.
3. Preparar venv e instalar dependencias verificadas:

```bash
python3.12 -m venv /opt/corevia/venv
/opt/corevia/venv/bin/python -m pip install -r /opt/corevia/current/requirements-lock.txt
/opt/corevia/venv/bin/python -m pip check
```

4. Completar `/etc/corevia/corevia.toml` y restringir permisos. Migrar la copia, o crear administrador en una instalación nueva, antes de abrir el acceso.
5. Revisar `deployment/linux/corevia.service`: rutas, usuario, permisos, directorios escribibles y límites. Copiarlo al directorio de unidades del sistema y validar **en ese servidor** con `systemd-analyze verify` una vez que existan usuarios y rutas.
6. Con autorización, ejecutar `systemctl daemon-reload` y luego `systemctl enable --now corevia`. Verificar `systemctl status corevia` y `journalctl -u corevia` sin compartir logs no revisados.
7. Comprobar desde el servidor `http://127.0.0.1:8080/healthz`. Este endpoint solo informa proceso/base disponible, sin datos laborales. Las pantallas de producción por HTTP directo deben rechazarse.
8. Configurar el proxy HTTPS según el apartado 10. Probar el arranque tras reiniciar el servidor en una ventana autorizada.

El bloqueo `corevia.service.lock` se libera al terminar el proceso, incluso si falla; no borrar el archivo para forzar una segunda instancia.

## 9. Instalación como servicio en Windows Server

1. Instalar Python 3.12 x64 para la cuenta del servicio según la política corporativa. Crear la estructura de carpetas y ACL del apartado 4. La carpeta del código no debe ser una carpeta personal ni de OneDrive.
2. Preparar el entorno:

```powershell
py -3.12 -m venv C:\Corevia\venv
C:\Corevia\venv\Scripts\python.exe -m pip install -r C:\Corevia\current\requirements-lock.txt
C:\Corevia\venv\Scripts\python.exe -m pip check
```

3. Completar el TOML en `C:\ProgramData\Corevia\config\corevia.toml`, migrar datos y verificar usuarios.
4. El servidor Python de consola no se registra directamente con `sc.exe`. Se proporciona `deployment/windows/CoreviaServicio.xml.example` para **WinSW**, un wrapper de servicios. Obtener una versión aprobada desde `https://github.com/winsw/winsw/releases`, verificar procedencia/firma/checksum con el procedimiento de Sistemas y no incorporar el ejecutable al repositorio.
5. Colocar el ejecutable como `CoreviaServicio.exe` y la plantilla revisada como `CoreviaServicio.xml` en una carpeta de servicio restringida. Ejecutar `CoreviaServicio.exe install` desde una consola autorizada. La plantilla inicia en modo **Manual** para permitir revisar la cuenta antes del primer arranque.
6. En Servicios de Windows, configurar una cuenta de servicio dedicada de privilegios mínimos (o el mecanismo corporativo que Sistemas confirme), con inicio de sesión como servicio y ACL necesarias. **No dejarlo ejecutando como LocalSystem/Administrador**. No guardar contraseñas en el XML. Si WinSW elegido requiere otro formato, adaptar siguiendo su documentación oficial antes de iniciar.
7. Configurar inicio automático y recuperación de errores una vez validada la cuenta. Iniciar con `CoreviaServicio.exe start` o desde Servicios. Comprobar `http://127.0.0.1:8080/healthz` desde el servidor y los logs de servicio.
8. Configurar IIS/ARR como proxy o el proxy corporativo aprobado. Las PC no deben acceder al backend 8080.
9. Probar reinicio del servidor y recuperación del servicio, sin usuario interactivo conectado. No usar `Iniciar-Corevia.bat` como servicio: ese archivo sigue reservado para las pruebas locales.

Las plantillas XML/PowerShell se entregan para revisión; no se probó su instalación en un Windows Server real.

## 10. HTTPS, DNS y restricción de red

**No hay que exponer Corevia a Internet.** Sistemas debe registrar el DNS interno, emitir/instalar el certificado, restringir la escucha del proxy a su interfaz interna y autorizar solo las subredes acordadas. No crear NAT, reglas públicas, túneles ni excepciones de certificados. Las restricciones de red de la aplicación son complementarias al firewall/proxy, no los sustituyen.

### Nginx

Revisar `deployment/proxy/nginx-corevia.conf.example`. Ajustar IP de escucha, DNS, certificados y `allow`. La subred debe coincidir con `allowed_networks`; el Host con `allowed_hosts`. Sobrescribir X-Forwarded-For con la IP del cliente y X-Forwarded-Proto con `https`; no concatenar cabeceras suministradas por el navegador. Validar `nginx -t` antes de recargar, solo en el servidor autorizado.

### IIS

Revisar `deployment/windows/web.config.example`. Requiere IIS, URL Rewrite y ARR aprobados. Crear sitio con binding HTTPS al DNS/IP internos y certificado corporativo. Configurar ARR para proxy con preservación del Host y permitir las variables `HTTP_X_FORWARDED_PROTO` y `HTTP_X_FORWARDED_FOR` que el sitio **sobrescribe**. Revisar con Sistemas el alcance de esas opciones si IIS aloja otros sitios; la plantilla no cambia configuración global automáticamente. Aplicar restricciones IP/firewall del sitio y validar headers. No publicar un binding público ni permitir que el cliente elija la IP reenviada.

No activar Flask debug ni el servidor de desarrollo. `run_server.py` utiliza Waitress con límites de cuerpo y tiempos. La confianza de proxy está limitada a loopback y un salto.

## 11. Copias de seguridad y restauración

### Copias

- Copia manual de administrador: Administración → Descargar copia.
- Copia programable consistente: `python manage.py backup` con la configuración de producción. Puede ejecutarse con el servicio activo; usa una conexión independiente y la API de backup SQLite. Genera `.sqlite` independiente de WAL, verifica integridad y escribe un manifiesto `.json` SHA-256.
- Linux: revisar `deployment/linux/corevia-backup.service` y `.timer`. Configurar usuario/permisos/rutas y comprobar la hora del sistema antes de habilitar el timer. No habilitarlo a ciegas en este entorno.
- Windows: usar el Programador de tareas con cuenta autorizada, «Ejecutar tanto si el usuario inició sesión como si no», y `deployment/windows/Backup-Corevia.ps1`. Revisar la política de ejecución/firma corporativa: no se recomienda ExecutionPolicy Bypass. Verificar el código de salida y el archivo generado.
- Definir y supervisar la retención con Sistemas. La herramienta **no borra respaldos** automáticamente. Copiar después a un segundo destino autorizado/cifrado: una copia en el mismo disco no protege frente a la pérdida del servidor.
- Las copias incluyen usuarios con hashes, historial, auditoría, ajustes y todos los períodos. No incluyen contraseñas en texto claro ni sesiones activas. Son datos personales protegidos: permisos, cifrado y transporte seguro también aplican al backup.

### Restauración

1. Confirmar incidente, copia y autorización con RR. HH.; detener nuevas cargas y avisar a los usuarios. Una restauración vuelve al estado de la copia y no puede recuperar operaciones posteriores que no estén respaldadas.
2. Detener el servicio (Linux `systemctl stop corevia`; Windows desde Servicios/WinSW). La orden de restauración verifica el bloqueo de instancia y se niega si Corevia está en ejecución.
3. Bajo la configuración correcta del destino:

```bash
python manage.py restore /ruta-segura/corevia-copia.sqlite --confirm RESTAURAR
python manage.py check
```

4. Se valida la copia antes de modificar el destino; si hay base actual, se guarda una copia `antes-restauracion-*`. La operación usa la API SQLite, conserva una vía de recuperación y revoca sesiones. No descargar/editar `-wal` ni `-shm` manualmente.
5. Iniciar el servicio, ingresar con una cuenta que exista en la copia y comprobar conteos, saldos y roles. Conservar evidencia de la prueba sin capturas ni nombres en tickets públicos.

La restauración web está deshabilitada en producción para evitar que reemplace información mientras otra persona trabaja. Sigue disponible en modo local.

## 12. Registros, monitoreo y datos personales

`corevia.log` rota en archivos de hasta 2 MB, con cinco históricos. Los errores inesperados devuelven una referencia y registran tipo de error/ubicación de código, sin cuerpo de solicitud, contraseñas, cookies, nombres de empleados ni el texto arbitrario de excepciones. La auditoría laboral se guarda en la base y es visible solo para administradores. Restringir también los logs del proxy y de WinSW/systemd; la configuración de Nginx propuesta omite query strings.

Supervisar salud del servicio, espacio de disco, errores 500/503, bloqueo SQLite, antigüedad de la última copia, vencimiento del certificado y restauraciones de prueba. Una cola persistente de escrituras o una carga que exceda el piloto obliga a revisar capacidad y posible PostgreSQL, no a levantar réplicas sobre SQLite.

No enviar bases, Excel, credenciales o logs sin revisar a GitHub, servicios externos ni tickets públicos. No hay telemetría externa incorporada.

## 13. Acceso directo Corevia en las PC

Las PC necesitan solo la URL HTTPS interna y la confianza del certificado. Sistemas puede distribuir un acceso «Corevia» por su mecanismo corporativo, o ejecutar para cada usuario:

```powershell
.\deployment\windows\Crear-Acceso-Corevia.ps1 -Url https://corevia.interno.example/
```

El script copia `static/brand/corevia.ico` a `%LOCALAPPDATA%\Corevia` y crea `Corevia.url` en el escritorio del usuario actual, abriendo el navegador predeterminado. No guarda credenciales ni instala Python/una base local. Respetar la política de firma de scripts de la empresa. El `.ico` se incluye en seis tamaños, derivado del isologo del proyecto. Para Linux de escritorio, Sistemas puede crear un lanzador `.desktop` equivalente que abra la URL con `xdg-open`, con nombre Corevia e ícono corporativo.

## 14. Actualizaciones sin perder información

1. Probar la nueva versión en un entorno separado con datos ficticios o una copia autorizada y protegida; nunca apuntar las pruebas a producción.
2. Anunciar ventana de mantenimiento y congelar cargas. Detener el servicio, crear una copia verificada y conservar código, configuración y dependencias de la versión anterior.
3. Descargar/extraer el commit aprobado en una carpeta de release nueva. **No borrar ni copiar encima de datos, claves, copias o logs**. No usar `git reset/clean` sobre directorios que contengan datos.
4. Instalar `requirements-lock.txt` en el entorno que se vaya a utilizar; conservar o recrear el entorno anterior para contingencias. Actualizar `current` solo con el servicio detenido.
5. Arrancar la nueva versión. Las migraciones compatibles preservan datos; antes de ampliar un esquema anterior se guarda una copia automática. Confirmar integridad, acceso, registros, saldos y permisos antes de reabrir cargas.
6. Si falla, mantener el servicio detenido y la copia intacta. No iniciar una versión vieja contra una base ya migrada: usar una restauración compatible con la versión elegida, ensayada en el entorno de prueba. Sistemas debe coordinar la recuperación; los archivos fuente originales y el respaldo previo permiten investigar sin pérdida del origen. No restaurar una copia previa después de reabrir cargas sin contabilizar las operaciones nuevas.
7. Registrar commit, fecha, resultado y responsable. Mantener backups fuera de las carpetas de releases.

Para actualizar una PC de prueba local desde una versión anterior, copiar **todo el código nuevo**, incluidos `corevia/`, `run_server.py` y `manage.py`, además de `app.py`, `static/` y `templates/`; conservar `data` y `.venv`. Instalar dependencias y reiniciar. Los nombres/claves antiguas de cookies se invalidan: será necesario ingresar nuevamente, pero no se borran usuarios ni datos laborales.

## 15. Pruebas y aceptación antes de habilitar usuarios

Comandos de desarrollo, siempre con datos temporales y fuera de producción:

```bash
python -m unittest discover -s tests -v
# Opcional: requiere openssl, genera certificados de prueba temporales.
python tests/https_smoke.py
# Opcional: requiere Playwright y Chromium de desarrollo, no para los usuarios.
node tests/browser_opening.cjs
```

Las pruebas verifican funcionalidades existentes, roles/CSRF, cookies y sesiones revocables, límites de login persistentes, revocación mientras una escritura espera, conflictos entre usuarios, copias WAL/migración sin sobrescritura y bloqueo de restauración durante servicio activo. La prueba HTTPS utiliza un certificado temporal explícitamente confiado y verifica el nombre del servidor; no desactiva TLS.

En el servidor elegido quedan por realizar: instalación nativa del servicio, proxy/certificado corporativo, ACL/firewall reales, reinicio, restauración completa, prueba desde dos PC y carga esperada. Criterios de aceptación: Gerencia puede consultar sin escribir; RR. HH. guarda y la otra PC ve el cambio; un formulario obsoleto no sobrescribe; vacaciones y licencias mantienen cálculos separados; el servicio inicia sin usuario conectado; copia y restauración están verificadas. Esta preparación no es una certificación de capacidad ni una auditoría de seguridad independiente.
