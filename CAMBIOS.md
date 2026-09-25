# Cambios de la versión 2.0

Esta versión amplía el aplicativo para cubrir los requerimientos descritos en el documento del trabajo de grado y corrige los defectos encontrados en las pruebas de la versión anterior.

## Defectos corregidos

| Defecto en la versión anterior | Corrección |
|---|---|
| El botón «Salir» devolvía error 405 (Django 5+ exige POST) | El cierre de sesión es un formulario POST con token CSRF |
| El stock nunca se descontaba | Al crear el pedido se descuenta (reserva) y al cancelarlo se devuelve; cada cambio queda como movimiento de inventario |
| Se podían agregar más unidades que el stock | El carrito valida el stock al agregar y al actualizar; el pedido lo vuelve a validar con bloqueo de registros |
| «Finalizar» con el carrito vacío creaba pedidos de $0 | Se redirige al carrito sin crear el pedido |
| Cualquiera podía descargar la factura de otro cliente | La factura exige sesión y solo muestra pedidos propios (el personal ve todas) |
| Factura o producto inexistente producían error 500 | Se responde 404 |
| El pedido no guardaba qué productos se compraron | Nuevo modelo `DetallePedido` |
| Tres imágenes estaban fuera de `media/` y no se mostraban | Se movieron a `media/productos/` |
| Clave secreta y DEBUG fijos en el código; base de datos en el repositorio | Variables de entorno y `.gitignore` |

## Requerimientos funcionales y dónde se implementan

| RF | Implementación |
|---|---|
| RF01 Registro de clientes | `forms.RegistroForm`, vista `registro` (correo, celular y aceptación de la política de datos en `PerfilCliente`) |
| RF02 Autenticación y roles | Autenticación de Django; grupos Administrador, Inventario y Ventas (`apps.py`) |
| RF03 Recuperación de contraseña | Vistas de Django en `/accounts/password_reset/` con plantillas propias |
| RF04 Catálogo por categorías | Modelo `Categoria`, vista `home` |
| RF05 Búsqueda y filtros | Vista `home` (texto, categoría, rango de precio y orden) |
| RF06 Detalle de producto | Vista `detalle_producto`; mensaje personalizado si `personalizable` |
| RF07–RF08 Carrito con validación de stock | `carrito.Carrito` (en sesión) |
| RF09 Creación de pedidos | `services.crear_pedido` (transacción atómica) |
| RF10 Registro de pagos | Modelo `Pago`; transferencia con comprobante o contra entrega |
| RF11 Seguimiento de pedidos | Vistas `mis_pedidos` y `detalle_pedido` (barra de progreso e historial) |
| RF12 Gestión de productos y categorías | Administración de Django (`admin.py`) |
| RF13 Inventario y alertas | `MovimientoInventario`, filtro «Stock bajo» y alertas en `/panel/` |
| RF14 Gestión de pedidos y pagos | Acciones del administrador: aprobar/rechazar pago, cambiar estado, cancelar |
| RF15 Reportes | Vista `reportes` en `/panel/reportes/` |
| RF16 Contacto | Enlaces a WhatsApp e Instagram en el pie de página |

## Reglas de negocio (services.py)

- Estados del pedido: Pendiente de pago → Pagado → En preparación → Enviado → Entregado. Se puede cancelar mientras esté pendiente de pago o pagado.
- Los pedidos contra entrega pueden pasar a preparación sin pago previo; el pago se aprueba automáticamente al marcarlos como entregados.
- Los pedidos por transferencia sin comprobante se cancelan después de `DL_HORAS_LIMITE_PAGO` horas (comando `cancelar_pedidos_vencidos`).

## Cómo actualizar una instalación existente

1. Conservar el archivo `db.sqlite3` actual y copiar encima los archivos nuevos.
2. `python manage.py migrate` (convierte los pedidos anteriores al nuevo estado «Pendiente de pago»).
3. `python manage.py cargar_categorias` (opcional).
4. Quitar la base de datos del repositorio: `git rm --cached delicias_liam/db.sqlite3`.
