"""Reglas de negocio de pedidos, pagos e inventario."""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (DetallePedido, HistorialEstado, MovimientoInventario, Pago,
                     Pedido, Producto)

# Transiciones permitidas entre estados del pedido
TRANSICIONES = {
    Pedido.PENDIENTE_PAGO: {Pedido.PAGADO, Pedido.EN_PREPARACION, Pedido.CANCELADO},
    Pedido.PAGADO: {Pedido.EN_PREPARACION, Pedido.CANCELADO},
    Pedido.EN_PREPARACION: {Pedido.ENVIADO},
    Pedido.ENVIADO: {Pedido.ENTREGADO, Pedido.EN_PREPARACION},
    Pedido.ENTREGADO: set(),
    Pedido.CANCELADO: set(),
}


def registrar_movimiento(producto, tipo, cantidad, usuario=None, motivo=''):
    """Aplica un movimiento de inventario al producto y lo deja registrado."""
    if tipo == MovimientoInventario.ENTRADA:
        producto.stock += cantidad
    elif tipo == MovimientoInventario.SALIDA:
        if cantidad > producto.stock:
            raise ValidationError(f'No hay stock suficiente de {producto.nombre}.')
        producto.stock -= cantidad
    else:  # AJUSTE
        if cantidad < 0:
            raise ValidationError('El stock no puede ser negativo.')
        producto.stock = cantidad
    producto.save(update_fields=['stock', 'actualizado'])
    return MovimientoInventario.objects.create(
        producto=producto, tipo=tipo, cantidad=cantidad, stock_resultante=producto.stock,
        usuario=usuario, motivo=motivo)


@transaction.atomic
def crear_pedido(usuario, carrito, datos_envio, metodo_pago):
    """Convierte el carrito en un pedido: verifica y reserva el stock, crea el
    detalle, registra el pago y vacía el carrito."""
    lineas = carrito.items()
    if not lineas:
        raise ValidationError('El carrito está vacío.')

    # Bloquear los productos para evitar vender dos veces la misma unidad
    ids = {l['producto'].id for l in lineas}
    productos = {p.id: p for p in Producto.objects.select_for_update().filter(id__in=ids)}
    requerido = {}
    for l in lineas:
        requerido[l['producto'].id] = requerido.get(l['producto'].id, 0) + l['cantidad']
    sin_stock = [productos[pid].nombre for pid, cant in requerido.items()
                 if not productos[pid].esta_disponible(cant)]
    if sin_stock:
        raise ValidationError('Sin stock suficiente: ' + ', '.join(sin_stock))

    subtotal = sum((productos[l['producto'].id].precio * l['cantidad'] for l in lineas), Decimal('0'))
    costo_envio = Decimal(settings.DELICIAS_LIAM['COSTO_ENVIO'])
    pedido = Pedido.objects.create(
        usuario=usuario, subtotal=subtotal, costo_envio=costo_envio, total=subtotal + costo_envio,
        **datos_envio)
    for l in lineas:
        p = productos[l['producto'].id]
        DetallePedido.objects.create(pedido=pedido, producto=p, cantidad=l['cantidad'],
                                     precio_unitario=p.precio, mensaje_personalizado=l['mensaje'])
    for pid, cant in requerido.items():
        registrar_movimiento(productos[pid], MovimientoInventario.SALIDA, cant, usuario,
                             f'Reserva para el pedido #{pedido.id}')
    Pago.objects.create(pedido=pedido, metodo=metodo_pago, monto=pedido.total)
    HistorialEstado.objects.create(pedido=pedido, estado=pedido.estado, usuario=usuario,
                                   comentario='Pedido creado por el cliente')
    carrito.vaciar()
    return pedido


@transaction.atomic
def cambiar_estado(pedido, nuevo_estado, usuario=None, comentario=''):
    if nuevo_estado == pedido.estado:
        return pedido
    if nuevo_estado not in TRANSICIONES[pedido.estado]:
        raise ValidationError(
            f'No se puede pasar de «{pedido.get_estado_display()}» a «{dict(Pedido.ESTADOS)[nuevo_estado]}».')
    pago = getattr(pedido, 'pago', None)
    if (pedido.estado == Pedido.PENDIENTE_PAGO and nuevo_estado == Pedido.EN_PREPARACION
            and (pago is None or pago.metodo != Pago.CONTRA_ENTREGA)):
        raise ValidationError('Solo los pedidos contra entrega pueden prepararse antes de confirmar el pago.')
    if nuevo_estado == Pedido.CANCELADO:
        for d in pedido.detalles.select_related('producto'):
            registrar_movimiento(d.producto, MovimientoInventario.ENTRADA, d.cantidad, usuario,
                                 f'Liberación por cancelación del pedido #{pedido.id}')
        if pago and pago.estado != Pago.APROBADO:
            pago.estado = Pago.RECHAZADO
            pago.observacion = pago.observacion or 'Pedido cancelado'
            pago.save()
    if nuevo_estado == Pedido.ENTREGADO and pago and pago.metodo == Pago.CONTRA_ENTREGA:
        pago.estado = Pago.APROBADO
        pago.fecha_verificacion = timezone.now()
        pago.save()
    pedido.estado = nuevo_estado
    pedido.save(update_fields=['estado', 'actualizado'])
    HistorialEstado.objects.create(pedido=pedido, estado=nuevo_estado, usuario=usuario, comentario=comentario)
    return pedido


def cancelar_pedido(pedido, usuario, comentario='Cancelado por el cliente'):
    if not pedido.puede_cancelarse:
        raise ValidationError('Este pedido ya no se puede cancelar.')
    return cambiar_estado(pedido, Pedido.CANCELADO, usuario, comentario)


def adjuntar_comprobante(pago, archivo, referencia=''):
    if pago.metodo != Pago.TRANSFERENCIA:
        raise ValidationError('Este pedido no requiere comprobante.')
    if pago.estado not in (Pago.PENDIENTE, Pago.RECHAZADO) or pago.pedido.estado != Pedido.PENDIENTE_PAGO:
        raise ValidationError('El pago de este pedido ya no admite comprobantes.')
    pago.comprobante = archivo
    pago.referencia = referencia
    pago.estado = Pago.EN_VERIFICACION
    pago.observacion = ''
    pago.save()
    return pago


@transaction.atomic
def aprobar_pago(pago, usuario):
    if pago.estado == Pago.APROBADO:
        return pago
    if pago.pedido.estado != Pedido.PENDIENTE_PAGO:
        raise ValidationError('Solo se pueden aprobar pagos de pedidos pendientes de pago.')
    pago.estado = Pago.APROBADO
    pago.fecha_verificacion = timezone.now()
    pago.save()
    cambiar_estado(pago.pedido, Pedido.PAGADO, usuario, 'Pago aprobado')
    return pago


def rechazar_pago(pago, usuario, observacion='Comprobante no válido'):
    if pago.estado == Pago.APROBADO:
        raise ValidationError('El pago ya fue aprobado.')
    pago.estado = Pago.RECHAZADO
    pago.observacion = observacion
    pago.fecha_verificacion = timezone.now()
    pago.save()
    HistorialEstado.objects.create(pedido=pago.pedido, estado=pago.pedido.estado, usuario=usuario,
                                   comentario=f'Pago rechazado: {observacion}')
    return pago


def cancelar_pedidos_vencidos(horas=None):
    """Cancela los pedidos por transferencia que superaron el tiempo límite sin comprobante."""
    horas = horas or settings.DELICIAS_LIAM['HORAS_LIMITE_PAGO']
    limite = timezone.now() - timedelta(hours=horas)
    vencidos = Pedido.objects.filter(
        estado=Pedido.PENDIENTE_PAGO, fecha__lt=limite,
        pago__metodo=Pago.TRANSFERENCIA, pago__estado__in=[Pago.PENDIENTE, Pago.RECHAZADO])
    cancelados = 0
    for pedido in vencidos:
        cambiar_estado(pedido, Pedido.CANCELADO, None, f'Cancelado automáticamente: sin pago en {horas} horas')
        cancelados += 1
    return cancelados
