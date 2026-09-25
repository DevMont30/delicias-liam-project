"""Pruebas funcionales de Delicias Liam.

Ejecutar con:  python manage.py test tienda
Cada prueba corresponde a un caso de la tabla de pruebas funcionales del documento (PF01...).
"""
import shutil
import tempfile
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Categoria, HistorialEstado, MovimientoInventario, Pago, Pedido, Producto
from . import services

MEDIA_TMP = tempfile.mkdtemp()
CLAVE = 'ClaveSegura#2026'


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class BaseTest(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_TMP, ignore_errors=True)

    def setUp(self):
        self.postres = Categoria.objects.create(nombre='Postres fríos')
        self.tortas = Categoria.objects.create(nombre='Tortas')
        self.brownie = Producto.objects.create(nombre='Brownies', descripcion='Chocolate', precio=Decimal('6000'),
                                               stock=10, categoria=self.postres)
        self.tarta = Producto.objects.create(nombre='Tarta de queso', descripcion='Horneada', precio=Decimal('8000'),
                                             stock=3, stock_minimo=3, categoria=self.postres, personalizable=True)
        self.torta = Producto.objects.create(nombre='Torta de zanahoria', descripcion='Con queso crema',
                                             precio=Decimal('9000'), stock=5, categoria=self.tortas)
        self.inactivo = Producto.objects.create(nombre='Producto inactivo', descripcion='x', precio=1, stock=5, activo=False)
        self.cliente = User.objects.create_user('cliente1', 'c1@correo.com', CLAVE, first_name='Ana')
        self.otro = User.objects.create_user('cliente2', 'c2@correo.com', CLAVE)
        self.admin = User.objects.create_superuser('admin', 'admin@correo.com', CLAVE)
        self.vendedor = User.objects.create_user('ventas', 'v@correo.com', CLAVE, is_staff=True)
        self.vendedor.groups.add(Group.objects.get(name='Ventas'))
        self.bodega = User.objects.create_user('inventario', 'i@correo.com', CLAVE, is_staff=True)
        self.bodega.groups.add(Group.objects.get(name='Inventario'))

    # utilidades
    def agregar(self, producto, cantidad=1, mensaje=''):
        return self.client.post(reverse('agregar', args=[producto.id]), {'cantidad': cantidad, 'mensaje': mensaje})

    def datos_checkout(self, **extra):
        datos = {'direccion': 'Calle 1 # 2-3', 'barrio': 'Chapinero', 'ciudad': 'Bogotá', 'guardar_direccion': 'on',
                 'nombre_recibe': 'Ana Pérez', 'telefono_contacto': '3001234567',
                 'fecha_entrega': (timezone.localdate() + timedelta(days=1)).isoformat(),
                 'metodo_pago': Pago.TRANSFERENCIA}
        datos.update(extra)
        return datos

    def comprar(self, metodo=Pago.TRANSFERENCIA):
        self.client.login(username='cliente1', password=CLAVE)
        self.agregar(self.brownie, 2)
        self.client.post(reverse('finalizar'), self.datos_checkout(metodo_pago=metodo))
        return Pedido.objects.filter(usuario=self.cliente).latest('id')


class CuentasTest(BaseTest):
    def test_pf01_registro_valido(self):
        r = self.client.post(reverse('registro'), {
            'first_name': 'Luis', 'last_name': 'Gómez', 'email': 'luis@correo.com', 'telefono': '3109876543',
            'username': 'luis', 'password1': 'OtraClave#2026', 'password2': 'OtraClave#2026',
            'acepta_tratamiento_datos': 'on'})
        self.assertRedirects(r, reverse('home'))
        u = User.objects.get(username='luis')
        self.assertEqual(u.perfil.telefono, '3109876543')
        self.assertTrue(u.perfil.acepta_tratamiento_datos)
        self.assertNotEqual(u.password, 'OtraClave#2026')  # contraseña cifrada

    def test_pf02_registro_correo_existente_y_sin_politica(self):
        r = self.client.post(reverse('registro'), {
            'first_name': 'X', 'last_name': 'Y', 'email': 'c1@correo.com', 'telefono': '3100000000',
            'username': 'nuevo', 'password1': 'OtraClave#2026', 'password2': 'OtraClave#2026'})
        self.assertEqual(r.status_code, 200)
        self.assertIn('email', r.context['form'].errors)
        self.assertIn('acepta_tratamiento_datos', r.context['form'].errors)
        self.assertFalse(User.objects.filter(username='nuevo').exists())

    def test_pf03_login_y_logout(self):
        r = self.client.post(reverse('login'), {'username': 'cliente1', 'password': CLAVE})
        self.assertRedirects(r, reverse('home'))
        r = self.client.post(reverse('logout'))
        self.assertEqual(r.status_code, 302)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_pf04_login_invalido(self):
        r = self.client.post(reverse('login'), {'username': 'cliente1', 'password': 'mala'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'no son correctos')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_pf05_recuperar_contrasena(self):
        r = self.client.post(reverse('password_reset'), {'email': 'c1@correo.com'})
        self.assertRedirects(r, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/accounts/reset/', mail.outbox[0].body)


class CatalogoTest(BaseTest):
    def test_pf06_catalogo_por_categoria(self):
        r = self.client.get(reverse('home'), {'categoria': self.tortas.slug})
        self.assertEqual(list(r.context['pagina']), [self.torta])
        r = self.client.get(reverse('home'))
        self.assertNotIn(self.inactivo, list(r.context['pagina']))

    def test_pf07_busqueda_y_filtro_precio(self):
        r = self.client.get(reverse('home'), {'q': 'queso'})
        self.assertEqual(set(r.context['pagina']), {self.tarta, self.torta})
        r = self.client.get(reverse('home'), {'precio_min': 7000, 'precio_max': 8500})
        self.assertEqual(list(r.context['pagina']), [self.tarta])
        r = self.client.get(reverse('home'), {'q': 'inexistente'})
        self.assertContains(r, 'No encontramos productos')

    def test_pf08_detalle_producto(self):
        r = self.client.get(reverse('producto', args=[self.tarta.id]))
        self.assertContains(r, 'Tarta de queso')
        self.assertContains(r, 'Mensaje para la tarjeta')  # producto personalizable
        self.assertEqual(self.client.get(reverse('producto', args=[self.inactivo.id])).status_code, 404)
        self.assertEqual(self.client.get(reverse('producto', args=[9999])).status_code, 404)


class CarritoTest(BaseTest):
    def test_pf09_agregar_y_calcular_total(self):
        self.agregar(self.brownie, 2)
        self.agregar(self.tarta, 1, 'Feliz cumpleaños')
        r = self.client.get(reverse('carrito'))
        self.assertEqual(r.context['total'], Decimal('20000'))
        self.assertContains(r, 'Feliz cumpleaños')

    def test_pf10_no_superar_stock(self):
        r = self.agregar(self.tarta, 5)
        self.assertRedirects(r, reverse('producto', args=[self.tarta.id]))
        self.agregar(self.tarta, 3)
        self.agregar(self.tarta, 1)  # ya no quedan unidades
        lineas = self.client.get(reverse('carrito')).context['lineas']
        self.assertEqual(sum(l['cantidad'] for l in lineas), 3)

    def test_pf11_actualizar_y_eliminar(self):
        self.agregar(self.brownie, 1)
        clave = self.client.get(reverse('carrito')).context['lineas'][0]['clave']
        self.client.post(reverse('actualizar'), {'clave': clave, 'cantidad': 4})
        self.assertEqual(self.client.get(reverse('carrito')).context['total'], Decimal('24000'))
        self.client.post(reverse('eliminar'), {'clave': clave})
        self.assertEqual(self.client.get(reverse('carrito')).context['lineas'], [])

    def test_pf12_producto_inexistente_o_por_get(self):
        self.assertEqual(self.client.post(reverse('agregar', args=[9999]), {'cantidad': 1}).status_code, 404)
        self.assertEqual(self.client.get(reverse('agregar', args=[self.brownie.id])).status_code, 405)


class PedidosTest(BaseTest):
    def test_pf13_finalizar_requiere_sesion_y_conserva_carrito(self):
        self.agregar(self.brownie, 1)
        r = self.client.get(reverse('finalizar'))
        self.assertRedirects(r, reverse('login') + '?next=' + reverse('finalizar'))
        self.client.login(username='cliente1', password=CLAVE)
        self.assertEqual(len(self.client.get(reverse('carrito')).context['lineas']), 1)

    def test_pf14_carrito_vacio_no_crea_pedido(self):
        self.client.login(username='cliente1', password=CLAVE)
        r = self.client.get(reverse('finalizar'))
        self.assertRedirects(r, reverse('carrito'))
        self.client.post(reverse('finalizar'), self.datos_checkout())
        self.assertFalse(Pedido.objects.exists())

    def test_pf15_realizar_pedido(self):
        pedido = self.comprar()
        self.assertEqual(pedido.estado, Pedido.PENDIENTE_PAGO)
        self.assertEqual(pedido.total, Decimal('12000'))
        self.assertEqual(pedido.detalles.get().cantidad, 2)
        self.assertEqual(pedido.pago.estado, Pago.PENDIENTE)
        self.brownie.refresh_from_db()
        self.assertEqual(self.brownie.stock, 8)  # stock reservado
        self.assertTrue(MovimientoInventario.objects.filter(producto=self.brownie, tipo='SALIDA').exists())
        self.assertEqual(self.client.get(reverse('carrito')).context['lineas'], [])
        self.assertEqual(self.cliente.direcciones.count(), 1)

    def test_pf16_stock_agotado_al_confirmar(self):
        self.client.login(username='cliente1', password=CLAVE)
        self.agregar(self.tarta, 3)
        Producto.objects.filter(id=self.tarta.id).update(stock=1)  # otra persona compró antes
        r = self.client.post(reverse('finalizar'), self.datos_checkout())
        self.assertRedirects(r, reverse('carrito'))
        self.assertFalse(Pedido.objects.exists())

    def test_pf17_subir_comprobante_y_aprobar_pago(self):
        pedido = self.comprar()
        archivo = SimpleUploadedFile('comprobante.png', b'\x89PNG\r\n\x1a\nfake', content_type='image/png')
        self.client.post(reverse('pedido', args=[pedido.id]), {'comprobante': archivo, 'referencia': 'ABC123'})
        pedido.pago.refresh_from_db()
        self.assertEqual(pedido.pago.estado, Pago.EN_VERIFICACION)
        services.aprobar_pago(pedido.pago, self.vendedor)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.PAGADO)
        self.assertEqual(pedido.pago.estado, Pago.APROBADO)

    def test_pf18_flujo_de_estados_y_historial(self):
        pedido = self.comprar()
        services.aprobar_pago(pedido.pago, self.vendedor)
        for estado in (Pedido.EN_PREPARACION, Pedido.ENVIADO, Pedido.ENTREGADO):
            services.cambiar_estado(pedido, estado, self.vendedor)
        self.assertEqual(pedido.estado, Pedido.ENTREGADO)
        self.assertEqual(HistorialEstado.objects.filter(pedido=pedido).count(), 5)
        r = self.client.get(reverse('pedido', args=[pedido.id]))
        self.assertContains(r, 'Entregado')
        with self.assertRaises(Exception):
            services.cambiar_estado(pedido, Pedido.CANCELADO, self.vendedor)  # transición no permitida

    def test_pf19_cancelar_libera_stock(self):
        pedido = self.comprar()
        self.client.post(reverse('cancelar_pedido', args=[pedido.id]))
        pedido.refresh_from_db()
        self.brownie.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.CANCELADO)
        self.assertEqual(self.brownie.stock, 10)

    def test_pf20_mis_pedidos_y_factura_solo_propios(self):
        pedido = self.comprar()
        otro = Pedido.objects.create(usuario=self.otro, total=5000)
        r = self.client.get(reverse('mis_pedidos'))
        self.assertEqual(list(r.context['pedidos']), [pedido])
        r = self.client.get(reverse('factura', args=[pedido.id]))
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(r.content.startswith(b'%PDF'))
        self.assertEqual(self.client.get(reverse('factura', args=[otro.id])).status_code, 404)
        self.assertEqual(self.client.get(reverse('pedido', args=[otro.id])).status_code, 404)
        self.assertEqual(self.client.get(reverse('factura', args=[9999])).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('factura', args=[pedido.id])).status_code, 302)

    def test_pf21_contra_entrega(self):
        pedido = self.comprar(metodo=Pago.CONTRA_ENTREGA)
        for estado in (Pedido.EN_PREPARACION, Pedido.ENVIADO, Pedido.ENTREGADO):
            services.cambiar_estado(pedido, estado, self.vendedor)
        pedido.pago.refresh_from_db()
        self.assertEqual(pedido.pago.estado, Pago.APROBADO)

    def test_pf22_cancelacion_automatica_por_vencimiento(self):
        pedido = self.comprar()
        Pedido.objects.filter(id=pedido.id).update(fecha=timezone.now() - timedelta(hours=72))
        self.assertEqual(services.cancelar_pedidos_vencidos(48), 1)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.CANCELADO)


class AdministracionTest(BaseTest):
    def test_pf23_crear_producto_con_stock_inicial(self):
        self.client.login(username='admin', password=CLAVE)
        r = self.client.post(reverse('admin:tienda_producto_add'), {
            'nombre': 'Almojábanas', 'categoria': self.postres.id, 'descripcion': 'Recién horneadas', 'precio': '7000',
            'stock': '12', 'stock_minimo': '3', 'activo': 'on',
            'movimientos-TOTAL_FORMS': '0', 'movimientos-INITIAL_FORMS': '0'})
        self.assertEqual(r.status_code, 302)
        p = Producto.objects.get(nombre='Almojábanas')
        self.assertEqual(p.stock, 12)
        self.assertContains(self.client.get(reverse('home')), 'Almojábanas')

    def test_pf24_movimiento_de_inventario_y_alerta(self):
        self.client.login(username='inventario', password=CLAVE)
        self.client.post(reverse('admin:tienda_movimientoinventario_add'),
                         {'producto': self.tarta.id, 'tipo': 'ENTRADA', 'cantidad': 7, 'motivo': 'Producción'})
        self.tarta.refresh_from_db()
        self.assertEqual(self.tarta.stock, 10)
        Producto.objects.filter(id=self.brownie.id).update(stock=2)
        r = self.client.get(reverse('panel'))
        self.assertContains(r, 'Brownies')  # aparece en alertas de inventario

    def test_pf25_permisos_por_rol(self):
        self.client.login(username='cliente1', password=CLAVE)
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 302)
        self.assertEqual(self.client.get(reverse('panel')).status_code, 302)
        self.client.login(username='inventario', password=CLAVE)
        self.assertEqual(self.client.get(reverse('admin:tienda_producto_changelist')).status_code, 200)
        self.assertEqual(self.client.get(reverse('admin:tienda_pago_changelist')).status_code, 403)
        self.assertEqual(self.client.get(reverse('reportes')).status_code, 403)
        self.client.login(username='ventas', password=CLAVE)
        self.assertEqual(self.client.get(reverse('admin:tienda_pago_changelist')).status_code, 200)

    def test_pf26_aprobar_pago_desde_admin(self):
        pedido = self.comprar()
        self.client.login(username='ventas', password=CLAVE)
        self.client.post(reverse('admin:tienda_pago_changelist'),
                         {'action': 'aprobar', '_selected_action': [pedido.pago.id]})
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.PAGADO)

    def test_pf27_reportes_de_ventas(self):
        pedido = self.comprar()
        services.aprobar_pago(pedido.pago, self.admin)
        self.client.login(username='admin', password=CLAVE)
        r = self.client.get(reverse('reportes'))
        self.assertEqual(r.context['resumen']['total'], Decimal('12000'))
        self.assertEqual(r.context['top'][0]['producto__nombre'], 'Brownies')
