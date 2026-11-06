# Corevia · Gestión de vacaciones y licencias

Aplicación web interna para una empresa argentina. Python 3.12+, Flask, SQLite y Waitress. Interfaz en español, sin servicios externos, fuentes remotas ni almacenamiento en la nube. Inspirada en la referencia de tarjetas suministrada.

## Empezar en Windows, paso a paso

1. Instalá **Python 3.12 o superior** desde https://www.python.org/downloads/windows/. En el instalador marcá **Add Python to PATH** e incluí el lanzador `py`.
2. Descargá este repositorio desde GitHub con **Code → Download ZIP**. Descomprimilo en una carpeta propia, por ejemplo `C:\Corevia`. No lo ejecutes dentro del ZIP, una carpeta compartida o una carpeta sincronizada con OneDrive.
3. Abrí la carpeta y hacé doble clic en **Iniciar-Corevia.bat**. La primera vez necesita Internet para descargar las dependencias desde PyPI. Esperá a que termine. No cierres la ventana que se abre.
4. El iniciador abre el navegador en `http://127.0.0.1:8080`. Si todavía no responde, esperá unos segundos y actualizá la página. Esa dirección funciona únicamente en tu propia computadora.
5. En el primer acceso, elegí un nombre de usuario y una contraseña de **al menos 12 caracteres**. Esa cuenta será administradora. No hay contraseñas predeterminadas. Conservá la contraseña en un lugar seguro.
6. Para probar, entrá en **Administración → Cargar demostración**. Se crean cuatro empleados ficticios, con identificadores `DEMO-1` a `DEMO-4`. Ningún dato real se incluye en el proyecto.
7. Revisá Calendario, Empleados y Vacaciones y licencias. El botón **Registrar ausencia** permite cargar vacaciones u otra licencia.
8. Antes de empezar con información real, hacé una copia si querés conservar la prueba y usá **Administración → Eliminar demostración**. Esto elimina únicamente los empleados marcados como demo y todos sus saldos y ausencias, aunque los hayas editado. Los empleados que agregaste manualmente se conservan.
9. Para cerrar, volvé a la ventana del iniciador, presioná **Ctrl+C**, confirmá si Windows pregunta, y cerrá la ventana. Cerrar el navegador no apaga el servidor. Para volver a trabajar, abrí de nuevo `Iniciar-Corevia.bat`.

**No está instalada en tu computadora por descargar el código.** Estos pasos preparan tu instalación local. El iniciador se proporciona para Windows; las pruebas de esta entrega se ejecutaron en Linux, no en Windows.

### Si aparece un problema

- «Python no se reconoce»: reinstalá Python con el lanzador `py` y abrí otra vez el iniciador.
- No abre el navegador: escribí `http://127.0.0.1:8080` en Edge o Chrome. Verificá que la ventana del iniciador siga abierta.
- El puerto está ocupado: cerrá otra instancia de Corevia. Pedí a Sistemas que cambie `RRHH_PORT` si ya lo usa otra aplicación.
- Error al instalar paquetes: revisá Internet y las políticas de la empresa. No desactives antivirus, certificados ni firewall. Mostrá el mensaje a Sistemas.
- No recordás la contraseña: no existe recuperación por correo. Pedí asistencia a Sistemas antes de modificar archivos o restaurar una copia.

## Uso diario

- **Empleados:** alta y edición, identificador único, sector, puesto, ingreso, estado y observaciones. Se puede dar de baja mediante el estado inactivo sin borrar el historial. Buscador, filtros y ordenación. Abrí el nombre para ver la ficha.
- **Saldos:** seleccioná el período en la barra superior y abrí la ficha. **Editar días asignados** permite reemplazar la sugerencia por el total anual exacto y ajustes con motivo. **Cargar / editar saldo inicial real** permite indicar los días que quedan a una fecha de corte, aunque ya se hayan tomado vacaciones. Son dos formas alternativas de calcular el saldo; no se suman entre sí. Ver el paso a paso más abajo. Cada modificación queda auditada y no se arrastran saldos entre años.
- **Ausencias:** fechas inclusivas y días corridos. Las solicitadas no descuentan; las aprobadas reservan días, y las aprobadas que ya terminaron se computan como utilizadas. Las disfrutadas descuentan como utilizadas; cuando hay saldo inicial real solo se descuentan los días posteriores a su fecha de corte. Las rechazadas y canceladas no descuentan. Un período en curso permanece reservado hasta finalizar. Las licencias no consumen vacaciones.
- **Validaciones:** impide ausencias activas superpuestas de una misma persona, fechas anteriores al ingreso y ausencias futuras marcadas como disfrutadas. Informa coincidencias en el sector y saldo insuficiente: un administrador puede confirmar la excepción y queda auditada. Para aprobar se requiere fecha y responsable.
- **Calendario:** lunes a domingo, navegación por mes/año, botón Hoy, filtros por sector, persona y tipo; bandas continuas en cada semana. Si hay más de tres filas, el enlace «+N más» abre las restantes. Las canceladas y rechazadas permanecen en el historial, sin mostrarse como ausencias en el calendario. Los indicadores siguen el mes actual de la computadora, aunque navegues a otro mes.
- **Períodos:** el selector de período controla las fichas y la exportación de saldos. El mes del calendario se navega por separado. El historial general permite ver todas las ausencias; la ficha muestra el año seleccionado.
- **Tipos de licencia:** agregar, renombrar o desactivar desde Administración. Vacaciones es un tipo protegido. Los registros de tipos desactivados se conservan.
- **Usuarios:** desde Administración creá una cuenta de Gerencia con «solo lectura». Puede consultar e imprimir/exportar listados. Solo los administradores pueden modificar datos, ver auditoría y realizar/restaurar copias. La autorización también se comprueba en el servidor.
- **Excel:** descarga un archivo `.xlsx` con empleados/saldos del período y otra hoja con el historial completo de ausencias. La exportación incluye todos los empleados, sin aplicar los filtros visuales. No contiene contraseñas. Se neutralizan fórmulas en los campos de texto.
- **Importación:** primera hoja `.xlsx`, encabezados exactos `code, first, last, sector, position, hired`. Un empleado por fila; `hired` debe ser una fecha Excel o texto `AAAA-MM-DD`. Ejemplo: `E001 | Ana | Pérez | Ventas | Analista | 2020-03-15`. Máximo 5000 empleados. Agrega empleados nuevos; por defecto omite los identificadores existentes sin cambiarlos; si desmarcás esa opción, un duplicado cancela toda la operación. Primero probá con datos ficticios y hacé una copia.
- **Impresión:** elegí el mes y los filtros, luego **Imprimir calendario**. El navegador permite seleccionar «Guardar como PDF». Para colores, habilitá gráficos de fondo. Los enlaces «más» deben consultarse en pantalla para el detalle completo de jornadas con muchas ausencias.

### Buscar empleados y vacaciones

Escribí un **nombre o apellido** y presioná **Buscar** o **Enter**. Se admiten coincidencias parciales, mayúsculas, espacios y nombres sin tildes (por ejemplo, `lucia` encuentra `Lucía`). También podés escribir apellido y nombre en cualquier orden. El identificador interno ya no se usa como criterio de búsqueda.

En Empleados se filtran las filas de la nómina; en Vacaciones y en Licencias se filtran sus respectivas tarjetas por el nombre o apellido de la persona. Cada sección conserva su propia búsqueda, sin aplicarla a las otras. Debajo se muestra la cantidad de resultados. **Limpiar** vuelve a mostrar los registros y quita los filtros de esa sección. En Empleados se mantienen las opciones de estado y ordenación; sector y tipo de ausencia se muestran solo donde corresponden al calendario o las ausencias.

## Espacio de trabajo: Vacaciones y Licencias separadas

En el menú hay dos secciones independientes:

- **Vacaciones:** incluye únicamente registros de tipo Vacaciones. Muestra por empleado la base del saldo, días utilizados, reservados y disponibles, más el historial del **período anual** seleccionado. El formulario de esta sección solo permite vacaciones. El saldo inicial y los ajustes se conservan y pueden editarse desde la ficha.
- **Licencias:** incluye todos los demás tipos (estudio, enfermedad, trámites personales, etc.). Muestra por empleado los días utilizados, reservados, pendientes y el total aprobado/disfrutado del **año calendario** seleccionado. No tiene una bolsa general de vacaciones ni descuenta sus días de ella. El formulario excluye el tipo Vacaciones.

Cada sección tiene su propia búsqueda por nombre/apellido y filtro de sector. Licencias también permite filtrar por tipo; sus totales se recalculan con esos filtros. El botón Excel exporta solo la sección abierta. Desde Empleados o Calendario, Excel conserva la exportación general.

**Ejemplo:** una licencia aprobada de estudio del 9 al 12 de noviembre suma **4 días reservados en Licencias**, y deja intacto el disponible de vacaciones. Lo mismo ocurre con trámites personales y enfermedad. Cuando termina, pasa al conteo de utilizados. Las pendientes se muestran aparte; las rechazadas o canceladas no suman al total.

El **Calendario** sigue reuniendo vacaciones y licencias con sus colores para conocer todas las ausencias. Los indicadores laterales también incluyen ambas. La nómina de **Empleados** conserva sus columnas de vacaciones y lo aclara expresamente; para ver los otros días, abrí Licencias. La ficha conserva ambos historiales separados.

Los registros existentes aparecen automáticamente en la sección que corresponde a su tipo. No hay que volver a cargarlos ni modificar la base para separarlos. Para actualizar esta versión, reemplazá `app.py`, `static/app.js`, `static/style.css` y `templates/index.html`, conservá `data` y reiniciá Corevia.

## Totales de licencias y nómina

Los indicadores laterales muestran **personas con ausencias** durante el mes actual y el siguiente, incluyendo vacaciones, estudio, trámites personales y cualquier otro tipo de licencia. Se desglosan vacaciones y licencias; el total cuenta cada persona una sola vez aunque tenga ambos tipos. Se incluyen Aprobadas y Disfrutadas; no Solicitadas, Rechazadas ni Canceladas.

La ficha del empleado muestra los días de licencia utilizados, reservados, pendientes y el desglose por tipo. La nómina resumida omite las columnas de sector/puesto y días de licencia, y usa los títulos Días utilizados, Días reservados y Días disponibles para sus columnas de vacaciones. Se suman los días corridos dentro del año calendario seleccionado, recortando los registros que cruzan de año. Las pendientes se muestran aparte y no forman parte del total aprobado/disfrutado. Estos días no consumen ni alteran el saldo de vacaciones. Excel incluye las mismas columnas de licencias.

### Importar la nómina que adjuntaste en tu computadora

1. Actualizá los archivos de Corevia, conservando tu carpeta `data` y haciendo una copia previa.
2. Entrá como administradora en **Administración → Importar empleados desde Excel**.
3. Seleccioná tu archivo **Empleados lista.xlsx**, que ya tiene los seis encabezados requeridos.
4. Dejá marcada **Omitir identificadores existentes sin modificarlos** y elegí Importar.
5. Se agregan solo los empleados nuevos. Si los cuatro identificadores ya existen, se omiten y se conservan sus vacaciones, licencias, saldos y datos laborales. Esta importación no actualiza los registros existentes ni inventa días tomados o saldos, porque el archivo contiene únicamente la nómina.

La nómina suministrada se cargó en la base local del entorno de trabajo, fuera de Git. Esa base no actualiza automáticamente una instalación en tu computadora. Los datos personales y el Excel no se incluyen en el repositorio ni en un ZIP de código.

Para Sistemas, la importación local repetible también está disponible con `.venv/bin/python -m flask --app app:create_app import-roster ruta.xlsx --skip-existing` (en Windows, usar `.venv\Scripts\python.exe`). No crea cuentas ni cambia las credenciales existentes.

## Cargar saldos reales y vacaciones de meses anteriores

No es necesario empezar con el total que sugiere la antigüedad. Podés registrar los días exactos validados para cada empleado y **cada período anual**, incluidos años anteriores y saldos de cero.

### Si ya sabés cuántos días le quedan

1. Abrí **Empleados**, buscá a la persona y seleccioná su nombre.
2. Elegí **Cargar / editar saldo inicial real**.
3. Indicá el **año al que corresponden los días**, los **días restantes**, la **fecha de corte** y un motivo (por ejemplo, «Saldo validado al comenzar a usar Corevia»).
4. La fecha de corte es **inclusive, al cierre de ese día**. El saldo que ingresás ya debe contemplar las vacaciones tomadas hasta esa fecha. No restes las vacaciones aprobadas posteriores: Corevia las reserva aparte.
5. Revisá la vista previa, marcá la confirmación y guardá. El año seleccionado se mostrará en la nómina y la ficha.
6. Desde la ficha, elegí **Registrar vacaciones ya tomadas**. También está disponible en **Vacaciones y licencias**. Indicá empleado, período anual, inicio, fin y observaciones. El estado será **Disfrutadas** y no se permiten fechas futuras.

**Ejemplo:** a Ana le quedan **7 días del período 2025 al 31/10/2026**. Cargá año 2025, saldo 7 y corte 31/10/2026. Podés registrar después sus vacaciones de agosto de 2026 imputadas a 2025: aparecerán en el historial y el calendario, pero el saldo seguirá en **7**. Si toma otros 3 días en noviembre, quedarán **4**.

- Los días hasta el corte se identifican como **ya incluidos** y no se descuentan otra vez, aunque cargues el historial después del saldo.
- Si una ausencia cruza el corte, se cuentan únicamente los días posteriores. Ejemplo: del 29/10 al 03/11, con corte 31/10, se descuentan 3 días.
- El año del período es independiente del año de las fechas: es posible usar en 2026 días correspondientes a 2025.
- Cambiar o cancelar vacaciones anteriores al corte **no modifica el saldo inicial declarado**. Si la corrección significa que el saldo real era otro, editá ese saldo y dejá el motivo. Cambiar o cancelar días posteriores sí recalcula el consumo.
- El contador de utilizados de la nómina muestra el historial registrado completo. La ficha distingue los días ya incluidos, los utilizados posteriores y los reservados. Un saldo inicial puede usarse sin haber cargado todavía todo el historial previo.
- Si hay vacaciones futuras aprobadas, el disponible puede ser menor que el saldo inicial: esas reservas se descuentan aparte. No las restes dos veces al cargar el saldo.
- La asignación anual original se conserva, pero mientras haya un saldo inicial real no se suma a este ni determina el disponible.
- Para otro año, cambiá el período dentro del formulario: se cargarán sus propios valores. No se copian automáticamente los saldos del año que estabas consultando.

### Cargar vacaciones futuras (por ejemplo, diciembre)

Usá **Registrar vacaciones / licencias** o **Registrar vacaciones futuras** en la ficha del empleado. Tanto Desde como Hasta admiten fechas futuras. Elegí **Solicitadas** si todavía están pendientes o **Aprobadas** para reservar días (requiere fecha y responsable de aprobación).

Si abriste **Registrar vacaciones ya tomadas**, arriba del formulario elegí **Vacaciones futuras / solicitudes / licencias** en «¿Qué querés registrar?». Se conservan empleado, período, fechas y observaciones, y el estado pasa de Disfrutadas a Solicitadas. El modo de historial limita ambas fechas a hoy: una ausencia futura no debe registrarse como ya disfrutada. La fecha final debe ser igual o posterior al inicio.

### Si conocés el total anual original

Usá **Editar días asignados**, ingresá el total anual exacto, los ajustes y el motivo. Si **no hay saldo inicial real activo**, Corevia restará todas las vacaciones disfrutadas/aprobadas y las reservas de ese período. Podés cargar las vacaciones antiguas con **Registrar vacaciones ya tomadas**.

Si querés abandonar un saldo inicial real, abrí ese formulario y elegí **Volver al cálculo por asignación anual…**, confirmá y dejá un motivo. Esto conserva el historial y vuelve a descontarlo del total anual. Revisá primero que ese total sea correcto.

### Actualizar una instalación Windows existente

1. Desde la versión que estás usando, descargá una copia de seguridad. Cerrá el servidor con **Ctrl+C**.
2. Descargá el ZIP actualizado de GitHub y descomprimilo en una carpeta temporal.
3. Copiá los archivos del programa sobre tu carpeta de Corevia. **Conservá tu carpeta `data` completa** (base de datos, clave y copias); no la borres ni la reemplaces. No copies bases de pruebas o de otras instalaciones.
4. Abrí de nuevo **Iniciar-Corevia.bat** y recargá la página del navegador (Ctrl+F5 si conserva la pantalla anterior).
5. Se agrega automáticamente una tabla para los saldos iniciales. Los empleados, vacaciones, licencias, saldos anuales y usuarios existentes se conservan y siguen calculándose como antes hasta que cargues un saldo inicial explícito.

Las copias de la primera versión también pueden restaurarse en esta versión. Restaurar una copia anterior al cambio no incluirá saldos iniciales que todavía no existían cuando se hizo esa copia. Las copias nuevas sí incluyen estos saldos. No restaures una copia nueva en una versión vieja del programa: desconocería el nuevo cálculo.

## Días adquiridos a la fecha y correspondientes al período

La nómina muestra tres conceptos separados:

- **Días adquiridos a la fecha:** orientación calculada hasta la fecha mostrada, o cantidad corregida manualmente por RR. HH.
- **Período / cierre de año:** asignación anual manual, si existe; en caso contrario, proyección orientativa al 31 de diciembre. No significa que todos esos días estén adquiridos hoy.
- **Base del saldo:** asignación y ajustes usados para calcular el disponible, o saldo inicial real previamente cargado. Las dos columnas anteriores no se suman entre sí ni se suman nuevamente a esta base.

Para corregirlos, hacé clic en los días adquiridos con el lápiz en la nómina, o abrí la ficha y elegí **Editar adquiridos y período**:

1. Elegí el período y la fecha del cómputo (dentro del período, hasta hoy).
2. Si disponés del registro de asistencia, cargá los **días trabajados / computables confirmados**. Deben contemplar las reglas aplicables sobre días computables, no simplemente los días de presencia.
3. Si necesitás corregir el resultado, completá **Días adquiridos: corrección manual**, incluso con cero. Dejalo vacío para usar la orientación calculada desde los días computables.
4. Para autorizar una cantidad en el saldo disponible, completá **Asignación exacta del período para el saldo**. Se conservan los ajustes, el historial y las reservas. Si hay un saldo inicial real, este sigue siendo la base y se modifica en su propio formulario.
5. Indicá el motivo de RR. HH. y guardá. La corrección queda registrada por empleado, año y fecha de cómputo. No se sobrescribe automáticamente al día siguiente: se muestra con su fecha hasta que RR. HH. la actualice.
6. Para volver a la orientación automática diaria, marcá esa opción en el formulario. La asignación anual que ya validaste no se elimina.

**Ejemplo ficticio:** ingreso el 08/10/2026; al 06/11/2026 hay 22 lunes a viernes inclusive. Bajo esa hipótesis se orienta **1 día** proporcional; al 31/12 se proyectan 3. Esto no acredita que haya trabajado esos días ni confirma su derecho efectivo. Con 20 días computables confirmados, el proporcional orientativo es 1; con menos de 20, cero. RR. HH. puede corregir ambas cantidades y la asignación usada para el saldo.

El modelo estima una jornada lunes a viernes, sin descontar feriados ni consultar asistencia, jornada parcial, ausencias o convenio. Para orientar el período completo compara los días computables con la mitad de los lunes a viernes del año; de no alcanzarse esa referencia, utiliza un día por cada veinte computables. La proyección supone continuidad bajo la misma jornada hasta fin de año. **Estos supuestos deben validarse** según los arts. 150–153 de la LCT, la jornada real y el convenio. Las estimaciones no habilitan automáticamente nuevos días para gastar ni reemplazan saldos ya validados.

Las correcciones y los días computables también se incluyen en las copias; Excel muestra adquiridos, fecha, proyección y origen. Las bases y copias anteriores se actualizan agregando una tabla, conservando sus datos y cálculos de saldo.

## Criterio orientativo de vacaciones

Se calcula la antigüedad al **31 de diciembre del período anual**, con los escalones generales de la LCT: hasta 5 años inclusive, 14 días; más de 5 y hasta 10, 21; más de 10 y hasta 20, 28; más de 20, 35. Se aplica una sugerencia automática únicamente cuando el ingreso es anterior o igual al 1 de enero del período.

**La fecha de ingreso no acredita los días efectivamente trabajados.** Para ingresos durante el año el sistema mantiene «Revisar» y deja la asignación para el saldo en cero hasta la intervención de RR. HH., pero muestra por separado adquiridos y proyección orientativos Debe determinarse si corresponde el período completo (art. 151) o el proporcional de un día por cada veinte efectivamente trabajados (art. 153), considerando las ausencias computables, el convenio y las condiciones particulares. El sistema no dispone de un registro de asistencia para decidirlo. Incluso las sugerencias completas requieren validación de RR. HH. Se pueden sobrescribir mediante una asignación y motivo.

No se trasladan vacaciones pendientes automáticamente. Registralas en su período de origen con un saldo inicial validado. Las reglas legales no sustituyen el asesoramiento laboral.

## Datos, copias y recuperación

Los datos quedan en `data\rrhh.sqlite` dentro de la carpeta de Corevia. `data\session.key` es la clave local para firmar sesiones. Ambos se generan automáticamente y se excluyen de Git. No borres esa carpeta. No se guarda información de empleados en GitHub. La base contiene información laboral y hashes de contraseñas: protegé la carpeta y las copias con los permisos de Windows y cifrado de disco que establezca Sistemas.

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
tests/test_app.py       Pruebas de las funciones existentes
tests/test_opening.py   Pruebas de saldos iniciales, historial y migración
tests/browser_opening.cjs  Prueba opcional del flujo en navegador
Iniciar-Corevia.bat        Iniciador Windows
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

Incluye empleados, calendario, vacaciones, licencias, saldos por año, saldos iniciales reales con corte e historial sin doble descuento, ajustes auditados, autenticación, roles, Excel, copias y restauración. No incluye integración con nómina/asistencia, confirmación automática del derecho proporcional sin datos de trabajo efectivo, criterios alternativos a días corridos, adjuntos médicos, recuperación de contraseña por correo, un instalador ejecutable firmado ni configuración de la red corporativa. Toda eliminación de demostración o cancelación exige confirmación; los empleados normales se inactivan y las ausencias se cancelan para preservar el historial.

## Identidad Corevia

La interfaz utiliza azul marino, azul brillante y celeste, con una adaptación vectorial del logo e isologo de referencia en `static/brand/`. El logo vectorial usa tipografía del sistema; puede reemplazarse por el archivo vectorial original para reproducir exactamente su tipografía. El iniciador anterior `Iniciar-Clara.bat` se conserva como acceso compatible al nuevo `Iniciar-Corevia.bat`. La carpeta de datos y el formato de las copias no cambian.

Para actualizar solo la marca no necesitás renombrar tu carpeta actual ni mover los datos. Copiá los archivos actualizados conservando `data` y usá `Iniciar-Corevia.bat`. El acceso anterior sigue funcionando como iniciador compatible.
