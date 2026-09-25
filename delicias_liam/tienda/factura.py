from io import BytesIO

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas


def _cop(valor):
    return '$ ' + f'{valor:,.0f}'.replace(',', '.')


def generar_pdf_factura(pedido):
    """Genera el comprobante de compra del pedido en PDF y devuelve los bytes."""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setTitle(f'Comprobante pedido {pedido.id} - Delicias Liam')
    ancho, alto = letter
    y = alto - 2 * cm

    pdf.setFillColor(colors.HexColor('#8E1F5A'))
    pdf.setFont('Helvetica-Bold', 20)
    pdf.drawString(2 * cm, y, 'DELICIAS LIAM')
    pdf.setFillColor(colors.black)
    pdf.setFont('Helvetica', 10)
    pdf.drawRightString(ancho - 2 * cm, y, f'Comprobante de compra No. {pedido.id}')
    y -= 1.2 * cm

    fecha = timezone.localtime(pedido.fecha).strftime('%d/%m/%Y %H:%M')
    cliente = pedido.usuario.get_full_name() or pedido.usuario.username
    pago = getattr(pedido, 'pago', None)
    datos = [
        ('Cliente', cliente), ('Fecha', fecha), ('Estado', pedido.get_estado_display()),
        ('Entrega', pedido.direccion_entrega or '-'),
        ('Fecha de entrega', pedido.fecha_entrega.strftime('%d/%m/%Y') if pedido.fecha_entrega else '-'),
        ('Método de pago', pago.get_metodo_display() if pago else '-'),
        ('Estado del pago', pago.get_estado_display() if pago else '-'),
    ]
    pdf.setFont('Helvetica', 10)
    for etiqueta, valor in datos:
        pdf.setFont('Helvetica-Bold', 10); pdf.drawString(2 * cm, y, f'{etiqueta}:')
        pdf.setFont('Helvetica', 10); pdf.drawString(5.5 * cm, y, str(valor)[:90])
        y -= 0.55 * cm

    y -= 0.4 * cm
    pdf.setFillColor(colors.HexColor('#FCE4F0'))
    pdf.rect(2 * cm, y - 0.15 * cm, ancho - 4 * cm, 0.65 * cm, stroke=0, fill=1)
    pdf.setFillColor(colors.black)
    pdf.setFont('Helvetica-Bold', 10)
    pdf.drawString(2.2 * cm, y, 'Producto')
    pdf.drawRightString(13 * cm, y, 'Cant.')
    pdf.drawRightString(16 * cm, y, 'Precio')
    pdf.drawRightString(ancho - 2.2 * cm, y, 'Subtotal')
    y -= 0.7 * cm
    pdf.setFont('Helvetica', 10)
    for d in pedido.detalles.select_related('producto'):
        pdf.drawString(2.2 * cm, y, d.producto.nombre[:55])
        pdf.drawRightString(13 * cm, y, str(d.cantidad))
        pdf.drawRightString(16 * cm, y, _cop(d.precio_unitario))
        pdf.drawRightString(ancho - 2.2 * cm, y, _cop(d.subtotal))
        if d.mensaje_personalizado:
            y -= 0.45 * cm
            pdf.setFont('Helvetica-Oblique', 8)
            pdf.drawString(2.6 * cm, y, f'Mensaje: {d.mensaje_personalizado[:90]}')
            pdf.setFont('Helvetica', 10)
        y -= 0.6 * cm
        if y < 4 * cm:
            pdf.showPage(); y = alto - 2 * cm; pdf.setFont('Helvetica', 10)

    pdf.line(2 * cm, y + 0.2 * cm, ancho - 2 * cm, y + 0.2 * cm)
    y -= 0.4 * cm
    for etiqueta, valor, negrita in (('Subtotal', pedido.subtotal, False), ('Envío', pedido.costo_envio, False),
                                      ('TOTAL', pedido.total, True)):
        pdf.setFont('Helvetica-Bold' if negrita else 'Helvetica', 12 if negrita else 10)
        pdf.drawRightString(16 * cm, y, etiqueta)
        pdf.drawRightString(ancho - 2.2 * cm, y, _cop(valor))
        y -= 0.6 * cm

    pdf.setFont('Helvetica', 9)
    pdf.drawString(2 * cm, 2 * cm, 'Gracias por comprar en Delicias Liam. Este documento no es una factura electrónica de venta.')
    pdf.save()
    return buffer.getvalue()
