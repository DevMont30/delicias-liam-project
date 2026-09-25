# Delicias Liam: tienda en línea

Plataforma e-commerce para el emprendimiento Delicias Liam, desarrollada como trabajo de grado de Ingeniería de Software (Universidad Manuela Beltrán).

**Tecnologías:** Python 3.12+ · Django 6.0 (patrón MVT) · Bootstrap 5.3 · SQLite en desarrollo / MySQL en producción · ReportLab (comprobantes PDF).

## Instalación

```bash
cd delicias_liam
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
python manage.py migrate
python manage.py cargar_categorias      # opcional: crea categorías sugeridas y asigna los productos
python manage.py createsuperuser        # si aún no existe
python manage.py runserver
```

- Tienda: http://127.0.0.1:8000/
- Panel del negocio: http://127.0.0.1:8000/panel/
- Administración: http://127.0.0.1:8000/admin/

## Roles

Al migrar se crean tres grupos. Asígnelos a cada colaborador desde **Administración > Usuarios** (marcar también «Es staff»):

| Grupo | Puede |
|---|---|
| Administrador | Todo el catálogo, pedidos, pagos, usuarios y reportes de ventas |
| Inventario | Productos, categorías y movimientos de inventario; ver pedidos |
| Ventas | Pedidos, confirmación de pagos y cambios de estado; ver productos |

## Configuración

Los datos del negocio y la seguridad se configuran con variables de entorno (ver `config/settings.py`):

| Variable | Uso |
|---|---|
| `DL_WHATSAPP`, `DL_INSTAGRAM` | Enlaces de contacto del pie de página |
| `DL_DATOS_TRANSFERENCIA` | Cuenta a la que los clientes transfieren |
| `DL_COSTO_ENVIO`, `DL_HORAS_LIMITE_PAGO` | Costo de envío y horas para pagar antes de la cancelación automática |
| `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS` | Seguridad en producción |
| `DB_ENGINE=mysql`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | Usar MySQL (instalar `mysqlclient`) |

Tarea programada recomendada (una vez al día):

```bash
python manage.py cancelar_pedidos_vencidos
```

## Pruebas

```bash
python manage.py test tienda
```

La suite contiene 27 pruebas funcionales (PF01 a PF27) que cubren registro, catálogo, carrito, pedidos, pagos, inventario, permisos y reportes.
