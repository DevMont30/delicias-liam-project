from django.db import migrations


def migrar_pedidos(apps, schema_editor):
    """Adapta los pedidos creados con la versión anterior del aplicativo."""
    Pedido = apps.get_model('tienda', 'Pedido')
    Historial = apps.get_model('tienda', 'HistorialEstado')
    for p in Pedido.objects.all():
        if p.estado == 'Pendiente':
            p.estado = 'PENDIENTE_PAGO'
        if not p.subtotal:
            p.subtotal = p.total
        p.save(update_fields=['estado', 'subtotal'])
        if not Historial.objects.filter(pedido=p).exists():
            Historial.objects.create(pedido=p, estado=p.estado, fecha=p.fecha,
                                     comentario='Pedido creado con la versión anterior del aplicativo')


def revertir(apps, schema_editor):
    Pedido = apps.get_model('tienda', 'Pedido')
    Pedido.objects.filter(estado='PENDIENTE_PAGO').update(estado='Pendiente')


class Migration(migrations.Migration):
    dependencies = [('tienda', '0003_ampliacion_modelo')]
    operations = [migrations.RunPython(migrar_pedidos, revertir)]
