# Validación de la primera versión

Entorno: Linux, Python 3.12.14, Node 24.22.1 para comprobar JavaScript, Chromium del sistema mediante Playwright. Datos exclusivamente ficticios en bases temporales.

## Pruebas automatizadas

Comando: `.venv/bin/python -m unittest discover -s tests -v`

Nueve pruebas de integración y lógica:

- Escalones de antigüedad al 31/12, ingresos parciales y días inclusivos en año bisiesto.
- Saldo inicial y ajustes, solicitudes pendientes, aprobaciones, consumo, cancelación y separación de años.
- Advertencia y confirmación de saldo insuficiente; licencias sin descuento de vacaciones.
- Reservas futuras y liberación por rechazo; cancelación de registros de empleados inactivos.
- Fechas inválidas, aprobación incompleta y prevención de marcar ausencias futuras como disfrutadas.
- Sesiones, CSRF y rechazo de todas las rutas de modificación para Gerencia.
- Importación Excel atómica ante duplicados y exportación legible.
- Persistencia al recrear la aplicación, copia/restauración y eliminación selectiva de demo.
- Gestión de tipos y neutralización de fórmulas en exportaciones.

También: `node --check static/app.js` y `.venv/bin/python -m pip check`.

## Prueba funcional en navegador

Servidor real Waitress sobre loopback, base temporal fuera del repositorio. Se verificaron creación del primer administrador, ingreso, carga de demo, calendario, apertura del detalle de ausencia, alta de un empleado desde el formulario y apertura de su ficha. Sin errores JavaScript. Se revisó una captura de escritorio y otra de ancho móvil. Una segunda comprobación confirmó que las siete columnas quedan dentro del calendario y las bandas se alinean con sus días.

## Límites

No se ejecutó Windows ni se probó el archivo .bat en ese sistema. No se configuró una red corporativa, HTTPS, firewall ni servicio de Windows. No se realizaron pruebas de carga, una auditoría de seguridad independiente ni validación de convenio colectivo. La fórmula legal es orientativa; los casos proporcionales requieren asignación manual validada por RR. HH. Los procesos y bases de prueba no forman parte de la aplicación distribuida.


## Ampliación: saldos iniciales e historial (6 de noviembre de 2026)

El entorno volvió a estar disponible. Se verificó lectura del checkout y acceso Git al repositorio remoto antes de modificar archivos. Se conservan las nueve pruebas anteriores y se agregan ocho en `tests/test_opening.py` (17 en total):

- Historial anterior al corte que no descuenta dos veces, incluidas edición y cancelación.
- Registros posteriores y períodos que atraviesan el corte; validación del saldo al editar.
- Saldo cero, reservas futuras y licencias sin consumo de vacaciones.
- Aislamiento de años, asignación anual editable, regreso explícito al cálculo anual y auditoría.
- Carga de historial antes o después de definir el saldo, modificación y persistencia.
- Validaciones de saldo/fecha/confirmación, bloqueo de superposición y permisos de Gerencia.
- Exportación con desglose, copia/restauración del nuevo saldo y retiro de demo.
- Actualización de una base anterior y restauración de una copia anterior sin pérdida de su cálculo e historial.

Prueba opcional reproducible en `tests/browser_opening.cjs`: requiere Playwright y Chromium como herramientas de desarrollo, sin agregarlas a las dependencias de la aplicación. Comando usado en Linux: `CHROMIUM_PATH=/usr/bin/chromium node tests/browser_opening.cjs`. El script inicia Waitress con una base temporal ficticia y la elimina al finalizar. Verifica alta, saldo real 7, historial previo sin descuento (sigue 7), consumo posterior de 3 días (queda 4), edición de la asignación de otro año sin mezclar saldos y ausencia de errores JavaScript. Se revisó la captura de la ficha con el desglose. Windows continúa pendiente de prueba directa.

## Identidad Corevia

Se actualizó la marca visible, la paleta a azul marino/azul/celeste, el logo vectorial y el favicon, y se agregó `Iniciar-Corevia.bat`. El iniciador anterior delega en el nuevo. Pasaron las 17 pruebas existentes, la comprobación de sintaxis JavaScript y el flujo de navegador con datos temporales. Se revisó la captura de la ficha con la nueva paleta. No cambia el esquema de datos por este ajuste visual. Los SVG son una adaptación de la referencia, con tipografía del sistema.


## Fechas de vacaciones futuras

Se añadió un selector de modo al formulario y un acceso directo desde la ficha a vacaciones futuras. El historial mantiene el límite de hoy en ambas fechas; el modo normal no tiene ese límite y valida el orden de fechas. El cambio de modo conserva los datos y pasa de Disfrutadas a Solicitadas. La prueba de navegador `tests/browser_opening.cjs` comprueba que se mantienen inicio y observaciones, habilita la fecha final de diciembre, aprueba el registro y reserva dos días sin sumarlos a los disfrutados.


## Adquiridos a la fecha y período al cierre

Se conservan las 17 pruebas y se agregan seis (23 en total). Cubren el caso ficticio de ingreso 08/10/2026 y cómputo 06/11/2026 (22 lunes a viernes; 1 día proporcional orientativo; proyección 3), límites de 19/20 computables, umbral orientativo de período completo y separación de años. También verifican corrección manual y cero, días confirmados, reinicio al cálculo diario, asignación anual independiente, conservación de saldo inicial, permisos de lectura, exportación, copias y migración de esquema anterior. La prueba de navegador verifica edición desde la nómina, adquiridos manuales 1 y asignación anual 14 manteniendo el saldo inicial existente; se revisa la ficha con los conceptos separados. Se mantienen las comprobaciones de saldos históricos y vacaciones futuras. No se acredita asistencia real ni se valida un convenio: las sugerencias se identifican como orientativas.


## Buscadores por nombre y apellido

El formulario ahora tiene Buscar, envío con Enter y Limpiar. La búsqueda usa únicamente nombres y apellidos normalizados; cada sección guarda su consulta por separado. Empleados no recibe los filtros de sector/tipo de otra sección. Se añadió contador de resultados y mensaje de nómina sin coincidencias. La prueba de navegador con cinco empleados ficticios comprueba envío por botón y Enter en nómina y ausencias, apellidos, tildes, mayúsculas, espacios, orden de palabras, cero coincidencias, exclusión de identificadores, limpieza y aislamiento entre secciones; también verifica la combinación con sector y tipo en ausencias. Pasó junto con los flujos existentes de saldos e historial, sin errores JavaScript.


## Totales de licencias e importación repetible

Pasaron 27 pruebas automatizadas (23 anteriores y cuatro nuevas). Se verifican indicadores de mes actual/siguiente con vacaciones y distintos tipos de licencia, personas únicas, exclusión de pendientes/canceladas, suma de días por año calendario y tipo, cruces de año, Excel y ausencia de descuento en vacaciones. La importación omite existentes solo cuando se solicita, conserva sus datos y permite repetirla por API o CLI. Las pruebas usan datos ficticios. El archivo de nómina autorizado contiene cuatro registros válidos y únicos; se importaron a la base local ignorada por Git y se repitió la carga con resultado cero nuevos/cuatro omitidos. No se incorporaron el Excel ni datos personales al repositorio.

La prueba en Chromium también confirmó un indicador mensual con cuatro personas: dos con vacaciones y dos con licencias, y ocho días de licencia en la fila de un empleado ficticio. Los demás flujos del navegador continuaron pasando sin errores JavaScript.
