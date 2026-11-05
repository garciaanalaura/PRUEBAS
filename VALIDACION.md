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
