from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class Categoria(models.Model):
    nombre = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True, blank=True)
    descripcion = models.CharField(max_length=255, blank=True)
    activa = models.BooleanField(default=True)
    orden = models.PositiveSmallIntegerField(default=0, help_text='Orden en que se muestra en la tienda.')

    class Meta:
        ordering = ['orden', 'nombre']
        verbose_name = 'categoría'
        verbose_name_plural = 'categorías'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nombre)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='productos', verbose_name='categoría')
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField('descripción')
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField(default=0)
    stock_minimo = models.PositiveIntegerField('stock mínimo', default=3,
                                               help_text='Al llegar a este valor se genera una alerta de stock bajo.')
    imagen = models.ImageField(upload_to='productos/', blank=True, null=True)
    personalizable = models.BooleanField(default=False,
                                         help_text='Permite que el cliente escriba un mensaje para la tarjeta.')
    activo = models.BooleanField(default=True, help_text='Los productos inactivos no se muestran en la tienda.')
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    def esta_disponible(self, cantidad=1):
        return self.activo and self.stock >= cantidad

    @property
    def agotado(self):
        return self.stock <= 0

    @property
    def stock_bajo(self):
        return 0 < self.stock <= self.stock_minimo

    @property
    def estado_inventario(self):
        if not self.activo:
            return 'Inactivo'
        if self.agotado:
            return 'Agotado'
        if self.stock_bajo:
            return 'Stock bajo'
        return 'Disponible'


class MovimientoInventario(models.Model):
    ENTRADA = 'ENTRADA'
    SALIDA = 'SALIDA'
    AJUSTE = 'AJUSTE'
    TIPOS = [(ENTRADA, 'Entrada'), (SALIDA, 'Salida'), (AJUSTE, 'Ajuste (fija el stock)')]

    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='movimientos')
    tipo = models.CharField(max_length=10, choices=TIPOS, default=ENTRADA)
    cantidad = models.IntegerField(help_text='En un ajuste, corresponde al nuevo stock total.')
    stock_resultante = models.IntegerField(editable=False, default=0)
    motivo = models.CharField(max_length=150, blank=True)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha']
        verbose_name = 'movimiento de inventario'
        verbose_name_plural = 'movimientos de inventario'

    def __str__(self):
        return f'{self.get_tipo_display()} de {self.cantidad} - {self.producto}'


class PerfilCliente(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    telefono = models.CharField('teléfono', max_length=20, blank=True)
    acepta_tratamiento_datos = models.BooleanField(default=False)
    fecha_aceptacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'perfil de cliente'
        verbose_name_plural = 'perfiles de cliente'

    def __str__(self):
        return f'Perfil de {self.usuario.username}'


class Direccion(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='direcciones')
    direccion = models.CharField('dirección', max_length=150)
    barrio = models.CharField(max_length=80, blank=True)
    ciudad = models.CharField(max_length=60, default='Bogotá')
    indicaciones = models.CharField(max_length=200, blank=True)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creada']
        verbose_name = 'dirección'
        verbose_name_plural = 'direcciones'

    def __str__(self):
        partes = [self.direccion, self.barrio, self.ciudad]
        return ', '.join(p for p in partes if p)


class Pedido(models.Model):
    PENDIENTE_PAGO = 'PENDIENTE_PAGO'
    PAGADO = 'PAGADO'
    EN_PREPARACION = 'EN_PREPARACION'
    ENVIADO = 'ENVIADO'
    ENTREGADO = 'ENTREGADO'
    CANCELADO = 'CANCELADO'
    ESTADOS = [
        (PENDIENTE_PAGO, 'Pendiente de pago'),
        (PAGADO, 'Pagado'),
        (EN_PREPARACION, 'En preparación'),
        (ENVIADO, 'Enviado'),
        (ENTREGADO, 'Entregado'),
        (CANCELADO, 'Cancelado'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pedidos')
    estado = models.CharField(max_length=20, choices=ESTADOS, default=PENDIENTE_PAGO)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    costo_envio = models.DecimalField('costo de envío', max_digits=10, decimal_places=2, default=Decimal('0'))
    total = models.DecimalField(max_digits=10, decimal_places=2)
    # Datos de entrega (se copian al pedido para conservarlos aunque cambie la dirección del cliente)
    nombre_recibe = models.CharField('nombre de quien recibe', max_length=120, blank=True)
    telefono_contacto = models.CharField('teléfono de contacto', max_length=20, blank=True)
    direccion_entrega = models.CharField('dirección de entrega', max_length=300, blank=True)
    fecha_entrega = models.DateField('fecha de entrega deseada', null=True, blank=True)
    notas = models.CharField(max_length=300, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fecha']
        permissions = [('ver_reportes', 'Puede ver los reportes de ventas')]

    def __str__(self):
        return f'Pedido #{self.id} - {self.usuario.username}'

    @property
    def puede_cancelarse(self):
        return self.estado in (self.PENDIENTE_PAGO, self.PAGADO)

    @property
    def paso_actual(self):
        """Posición del pedido en el flujo normal (para la barra de progreso)."""
        orden = [self.PENDIENTE_PAGO, self.PAGADO, self.EN_PREPARACION, self.ENVIADO, self.ENTREGADO]
        return orden.index(self.estado) if self.estado in orden else -1


class DetallePedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='detalles')
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    mensaje_personalizado = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = 'detalle de pedido'
        verbose_name_plural = 'detalles de pedido'

    @property
    def subtotal(self):
        return self.precio_unitario * self.cantidad

    def __str__(self):
        return f'{self.cantidad} x {self.producto}'


class Pago(models.Model):
    TRANSFERENCIA = 'TRANSFERENCIA'
    CONTRA_ENTREGA = 'CONTRA_ENTREGA'
    METODOS = [
        (TRANSFERENCIA, 'Transferencia (Nequi, Daviplata o cuenta bancaria)'),
        (CONTRA_ENTREGA, 'Pago contra entrega'),
    ]
    PENDIENTE = 'PENDIENTE'
    EN_VERIFICACION = 'EN_VERIFICACION'
    APROBADO = 'APROBADO'
    RECHAZADO = 'RECHAZADO'
    ESTADOS = [
        (PENDIENTE, 'Pendiente'),
        (EN_VERIFICACION, 'En verificación'),
        (APROBADO, 'Aprobado'),
        (RECHAZADO, 'Rechazado'),
    ]

    pedido = models.OneToOneField(Pedido, on_delete=models.CASCADE, related_name='pago')
    metodo = models.CharField('método', max_length=20, choices=METODOS)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(max_length=20, choices=ESTADOS, default=PENDIENTE)
    comprobante = models.FileField(upload_to='comprobantes/', blank=True, null=True)
    referencia = models.CharField(max_length=60, blank=True)
    observacion = models.CharField('observación', max_length=200, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)
    fecha_verificacion = models.DateTimeField('fecha de verificación', null=True, blank=True)

    def __str__(self):
        return f'Pago del pedido #{self.pedido_id} ({self.get_estado_display()})'


class HistorialEstado(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='historial')
    estado = models.CharField(max_length=20, choices=Pedido.ESTADOS)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    comentario = models.CharField(max_length=200, blank=True)
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['fecha']
        verbose_name = 'historial de estado'
        verbose_name_plural = 'historial de estados'

    def __str__(self):
        return f'#{self.pedido_id} {self.get_estado_display()}'
