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
