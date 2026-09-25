"""Carrito de compras almacenado en la sesión del usuario.

Cada línea se identifica por el producto y el mensaje personalizado, de modo que
un mismo producto puede comprarse varias veces con mensajes distintos.
"""
from decimal import Decimal

from .models import Producto

CLAVE_SESION = 'carrito'


class StockInsuficiente(Exception):
    def __init__(self, producto, disponible):
        self.producto = producto
        self.disponible = disponible
        super().__init__(f'Solo hay {disponible} unidades de {producto.nombre}.')


class Carrito:
    def __init__(self, request):
        self.session = request.session
        datos = self.session.get(CLAVE_SESION)
        # Formato anterior ({id: cantidad}) o dato corrupto: se reinicia
        if not isinstance(datos, dict) or 'items' not in datos:
            datos = {'items': {}}
        self.datos = datos

    # --- utilidades internas ---
    @staticmethod
    def _clave(producto_id, mensaje):
        return f'{producto_id}|{mensaje.strip()}'

    def _guardar(self):
        self.session[CLAVE_SESION] = self.datos
        self.session.modified = True

    def cantidad_producto(self, producto_id, excluir_clave=None):
        return sum(i['cantidad'] for k, i in self.datos['items'].items()
                   if i['producto_id'] == producto_id and k != excluir_clave)

    # --- operaciones ---
    def agregar_item(self, producto, cantidad=1, mensaje=''):
        mensaje = (mensaje or '').strip() if producto.personalizable else ''
        clave = self._clave(producto.id, mensaje)
        en_carrito = self.cantidad_producto(producto.id)
        if not producto.activo or en_carrito + cantidad > producto.stock:
            raise StockInsuficiente(producto, max(producto.stock - en_carrito, 0))
        item = self.datos['items'].get(clave, {'producto_id': producto.id, 'cantidad': 0, 'mensaje': mensaje})
        item['cantidad'] += cantidad
        self.datos['items'][clave] = item
        self._guardar()

    def actualizar_item(self, clave, cantidad):
        item = self.datos['items'].get(clave)
        if item is None:
            return
        if cantidad <= 0:
            self.eliminar_item(clave)
            return
        producto = Producto.objects.get(id=item['producto_id'])
        otros = self.cantidad_producto(producto.id, excluir_clave=clave)
        if otros + cantidad > producto.stock:
            raise StockInsuficiente(producto, max(producto.stock - otros, 0))
        item['cantidad'] = cantidad
        self._guardar()

    def eliminar_item(self, clave):
        if clave in self.datos['items']:
            del self.datos['items'][clave]
            self._guardar()

    def vaciar(self):
        self.datos = {'items': {}}
        self._guardar()

    # --- consulta ---
    def items(self):
        """Devuelve las líneas del carrito con su producto. Elimina las que
        correspondan a productos borrados o desactivados."""
        ids = {i['producto_id'] for i in self.datos['items'].values()}
        productos = {p.id: p for p in Producto.objects.filter(id__in=ids, activo=True)}
        lineas, huerfanas = [], []
        for clave, item in self.datos['items'].items():
            producto = productos.get(item['producto_id'])
            if producto is None:
                huerfanas.append(clave)
                continue
            lineas.append({
                'clave': clave,
                'producto': producto,
                'cantidad': item['cantidad'],
                'mensaje': item.get('mensaje', ''),
                'subtotal': producto.precio * item['cantidad'],
            })
        for clave in huerfanas:
            del self.datos['items'][clave]
        if huerfanas:
            self._guardar()
        return lineas

    def calcular_total(self):
        return sum((l['subtotal'] for l in self.items()), Decimal('0'))

    def __len__(self):
        return sum(i['cantidad'] for i in self.datos['items'].values())

    def esta_vacio(self):
        return len(self.datos['items']) == 0
