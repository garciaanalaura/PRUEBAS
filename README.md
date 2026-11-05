# Clara · Gestión de vacaciones y licencias

Aplicación web interna para una empresa argentina. Python 3.12+, Flask, SQLite y Waitress. Interfaz en español, sin servicios externos, fuentes remotas ni almacenamiento en la nube. Inspirada en la referencia de tarjetas suministrada.

## Empezar en Windows, paso a paso

1. Instalá **Python 3.12 o superior** desde https://www.python.org/downloads/windows/. En el instalador marcá **Add Python to PATH** e incluí el lanzador `py`.
2. Descargá este repositorio desde GitHub con **Code → Download ZIP**. Descomprimilo en una carpeta propia, por ejemplo `C:\Clara`. No lo ejecutes dentro del ZIP, una carpeta compartida o una carpeta sincronizada con OneDrive.
3. Abrí la carpeta y hacé doble clic en **Iniciar-Clara.bat**. La primera vez necesita Internet para descargar las dependencias desde PyPI. Esperá a que termine. No cierres la ventana que se abre.
4. El iniciador abre el navegador en `http://127.0.0.1:8080`. Si todavía no responde, esperá unos segundos y actualizá la página. Esa dirección funciona únicamente en tu propia computadora.
5. En el primer acceso, elegí un nombre de usuario y una contraseña de **al menos 12 caracteres**. Esa cuenta será administradora. No hay contraseñas predeterminadas. Conservá la contraseña en un lugar seguro.
6. Para probar, entrá en **Administración → Cargar demostración**. Se crean cuatro empleados ficticios, con identificadores `DEMO-1` a `DEMO-4`. Ningún dato real se incluye en el proyecto.
7. Revisá Calendario, Empleados y Vacaciones y licencias. El botón **Registrar ausencia** permite cargar vacaciones u otra licencia.
8. Antes de empezar con información real, hacé una copia si querés conservar la prueba y usá **Administración → Eliminar demostración**. Esto elimina únicamente los empleados marcados como demo y todos sus saldos y ausencias, aunque los hayas editado. Los empleados que agregaste manualmente se conservan.
9. Para cerrar, volvé a la ventana del iniciador, presioná **Ctrl+C**, confirmá si Windows pregunta, y cerrá la ventana. Cerrar el navegador no apaga el servidor. Para volver a trabajar, abrí de nuevo `Iniciar-Clara.bat`.

**No está instalada en tu computadora por descargar el código.** Estos pasos preparan tu instalación local. El iniciador se proporciona para Windows; las pruebas de esta entrega se ejecutaron en Linux, no en Windows.

### Si aparece un problema

- «Python no se reconoce»: reinstalá Python con el lanzador `py` y abrí otra vez el iniciador.
- No abre el navegador: escribí `http://127.0.0.1:8080` en Edge o Chrome. Verificá que la ventana del iniciador siga abierta.
- El puerto está ocupado: cerrá otra instancia de Clara. Pedí a Sistemas que cambie `RRHH_PORT` si ya lo usa otra aplicación.
- Error al instalar paquetes: revisá Internet y las políticas de la empresa. No desactives antivirus, certificados ni firewall. Mostrá el mensaje a Sistemas.
- No recordás la contraseña: no existe recuperación por correo. Pedí asistencia a Sistemas antes de modificar archivos o restaurar una copia.

## Uso diario

- **Empleados:** alta y edición, identificador único, sector, puesto, ingreso, estado y observaciones. Se puede dar de baja mediante el estado inactivo sin borrar el historial. Buscador, filtros y ordenación. Abrí el nombre para ver la ficha.
- **Saldos:** seleccioná el período en la barra superior, abrí la ficha y elegí **Asignar / ajustar saldo**. Los días asignados incluyen el saldo inicial validado de ese año; el ajuste es el total adicional vigente y requiere motivo. No es una suma de movimientos: al editarlo reemplazás su valor anterior. Cada modificación queda en el registro de cambios. No se arrastran saldos entre años.
- **Ausencias:** fechas inclusivas y días corridos. Las solicitadas no descuentan; las aprobadas reservan días, y las aprobadas que ya terminaron se computan como utilizadas. Las disfrutadas descuentan como utilizadas; las rechazadas y canceladas no descuentan. Un período en curso permanece reservado hasta finalizar. Las licencias no consumen vacaciones.
- **Validaciones:** impide ausencias activas superpuestas de una misma persona, fechas anteriores al ingreso y ausencias futuras marcadas como disfrutadas. Informa coincidencias en el sector y saldo insuficiente: un administrador puede confirmar la excepción y queda auditada. Para aprobar se requiere fecha y responsable.
- **Calendario:** lunes a domingo, navegación por mes/año, botón Hoy, filtros por sector, persona y tipo; bandas continuas en cada semana. Si hay más de tres filas, el enlace «+N más» abre las restantes. Las canceladas y rechazadas permanecen en el historial, sin mostrarse como ausencias en el calendario. Los indicadores siguen el mes actual de la computadora, aunque navegues a otro mes.
- **Períodos:** el selector de período controla las fichas y la exportación de saldos. El mes del calendario se navega por separado. El historial general permite ver todas las ausencias; la ficha muestra el año seleccionado.
- **Tipos de licencia:** agregar, renombrar o desactivar desde Administración. Vacaciones es un tipo protegido. Los registros de tipos desactivados se conservan.
- **Usuarios:** desde Administración creá una cuenta de Gerencia con «solo lectura». Puede consultar e imprimir/exportar listados. Solo los administradores pueden modificar datos, ver auditoría y realizar/restaurar copias. La autorización también se comprueba en el servidor.
- **Excel:** descarga un archivo `.xlsx` con empleados/saldos del período y otra hoja con el historial completo de ausencias. La exportación incluye todos los empleados, sin aplicar los filtros visuales. No contiene contraseñas. Se neutralizan fórmulas en los campos de texto.
- **Importación:** primera hoja `.xlsx`, encabezados exactos `code, first, last, sector, position, hired`. Un empleado por fila; `hired` debe ser una fecha Excel o texto `AAAA-MM-DD`. Ejemplo: `E001 | Ana | Pérez | Ventas | Analista | 2020-03-15`. Máximo 5000 empleados. Agrega empleados nuevos; identificadores duplicados cancelan toda la operación. Primero probá con datos ficticios y hacé una copia.
- **Impresión:** elegí el mes y los filtros, luego **Imprimir calendario**. El navegador permite seleccionar «Guardar como PDF». Para colores, habilitá gráficos de fondo. Los enlaces «más» deben consultarse en pantalla para el detalle completo de jornadas con muchas ausencias.

## Criterio orientativo de vacaciones

Se calcula la antigüedad al **31 de diciembre del período anual**, con los escalones generales de la LCT: hasta 5 años inclusive, 14 días; más de 5 y hasta 10, 21; más de 10 y hasta 20, 28; más de 20, 35. Se aplica una sugerencia automática únicamente cuando el ingreso es anterior o igual al 1 de enero del período.

**La fecha de ingreso no acredita los días efectivamente trabajados.** Para ingresos durante el año el sistema muestra «Revisar» y deja la asignación automática en cero hasta la intervención de RR. HH. Debe determinarse si corresponde el período completo (art. 151) o el proporcional de un día por cada veinte efectivamente trabajados (art. 153), considerando las ausencias computables, el convenio y las condiciones particulares. El sistema no dispone de un registro de asistencia para decidirlo. Incluso las sugerencias completas requieren validación de RR. HH. Se pueden sobrescribir mediante una asignación y motivo.

No se trasladan vacaciones pendientes automáticamente. Registralas en su período de origen con un saldo inicial validado. Las reglas legales no sustituyen el asesoramiento laboral.

## Datos, copias y recuperación

Los datos quedan en `data\rrhh.sqlite` dentro de la carpeta de Clara. `data\session.key` es la clave local para firmar sesiones. Ambos se generan automáticamente y se excluyen de Git. No borres esa carpeta. No se guarda información de empleados en GitHub. La base contiene información laboral y hashes de contraseñas: protegé la carpeta y las copias con los permisos de Windows y cifrado de disco que establezca Sistemas.

1. Con sesión administradora, abrí **Administración → Descargar copia**.
2. Guardá el archivo `rrhh-AAAA-MM-DD.sqlite` en un destino autorizado, preferentemente separado de la computadora. La copia incluye usuarios, contraseñas cifradas mediante hash, empleados, ausencias, saldos y auditoría. No envíes copias por correo ni a servicios externos sin autorización.
3. Para recuperar, abrí **Restaurar copia**, seleccioná el archivo, escribí `RESTAURAR` y tu contraseña actual. La aplicación valida integridad y estructura.
4. La restauración reemplaza **toda** la base e invalida todas las sesiones existentes al renovar la clave de firma. Ingresá con una cuenta administradora y contraseña que existieran en la copia.
5. Antes de reemplazar, se conserva automáticamente `data\antes-restaurar-FECHA.sqlite`. Si elegiste una copia equivocada, podés restaurar ese archivo siguiendo el mismo procedimiento.

Las copias son manuales; se recomienda una al terminar cada jornada y antes de importaciones. Para automatizarlas, Sistemas debe programar copias consistentes con la API de SQLite, o detener el servicio antes de copiar el archivo. No copiar una base activa con herramientas que no garanticen consistencia.

## Instalación posterior en red interna (para Sistemas)

La arquitectura usa un único servidor HTTP y una sola SQLite local al servidor, no un archivo de base compartido por SMB. Las otras computadoras acceden por navegador; la interfaz refresca datos al guardar y al cambiar de período. Para ver cambios hechos por otra sesión, actualizar la página. Esta versión no tiene notificaciones push ni actualizaciones en tiempo real entre navegadores.

1. Definir un equipo interno autorizado, respaldo, política de acceso y responsables. Instalar Python y las dependencias en un entorno virtual.
2. Ubicar los datos en un disco local con permisos restringidos a la cuenta del servicio. Opcional: variable `RRHH_DATA` con una ruta absoluta. Mantener la hora y zona horaria del servidor correctamente configuradas para Argentina.
3. Iniciar con Waitress (`python app.py`). Por defecto escucha **solo en 127.0.0.1:8080** y no modifica firewall. `RRHH_HOST` y `RRHH_PORT` permiten elegir interfaz y puerto.
4. Para acceso de otras computadoras, Sistemas debe configurar **HTTPS** mediante un proxy inverso interno (por ejemplo IIS), certificados y reglas de acceso limitadas a la red autorizada. Mantener Waitress detrás de ese proxy y establecer la variable `RRHH_HTTPS=1` para activar cookies seguras antes de habilitar acceso por HTTPS. No habilitar HTTP con datos laborales en la red. No abrir puertos de Internet ni configurar NAT.
5. Crear cuentas individuales; Gerencia con rol lectura. Configurar un servicio de Windows y copias programadas bajo la política corporativa. No usar el servidor de desarrollo de Flask.
6. Probar simultaneidad, permisos, recuperación y capacidad según el tamaño real de la nómina. SQLite es apropiada para una primera instalación pequeña; mayor carga puede requerir migración a PostgreSQL.

Esta entrega no cambia configuraciones de red, no crea el servicio Windows ni configura HTTPS. Eso requiere intervención y autorización de Sistemas. Para una exposición multiusuario permanente también deben revisarse gestión de cuentas (cambio/recuperación/desactivación), bloqueo de intentos a nivel de servicio. La limitación de login actual es en memoria, para el proceso local.

## Desarrollo y estructura

```text
app.py                  Servidor, validaciones, persistencia y API
static/app.js           Calendario y formularios interactivos
static/style.css        Diseño adaptable e impresión
templates/index.html    Interfaz sin recursos externos
tests/test_app.py       Pruebas de integración y cálculos
Iniciar-Clara.bat        Iniciador Windows
requirements.txt        Dependencias directas
requirements-lock.txt   Versiones completas verificadas en Linux/Python 3.12
data/                   Datos locales, fuera de Git
```

```bash
python -m venv .venv
# Windows: .venv\Scripts\python.exe ; Linux: .venv/bin/python
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python app.py
```

No se requiere Node para usar la aplicación. `node --check static/app.js` es una comprobación adicional de sintaxis para desarrolladores. Las pruebas usan bases temporales y nunca cargan datos reales. No se requiere Internet para usar la aplicación después de instalar sus dependencias.

## Alcance de esta primera entrega

Incluye empleados, calendario, vacaciones, licencias, saldos por año, ajustes auditados, autenticación, roles, Excel, copias y restauración. No incluye integración con nómina/asistencia, cálculo automático del proporcional sin datos de trabajo efectivo, criterios alternativos a días corridos, adjuntos médicos, recuperación de contraseña por correo, un instalador ejecutable firmado ni configuración de la red corporativa. Toda eliminación de demostración o cancelación exige confirmación; los empleados normales se inactivan y las ausencias se cancelan para preservar el historial.
