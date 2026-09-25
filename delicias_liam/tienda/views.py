from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import services
from .carrito import Carrito, StockInsuficiente
from .factura import generar_pdf_factura
from .forms import AgregarCarritoForm, CheckoutForm, ComprobanteForm, FiltroReporteForm, RegistroForm
from .models import Categoria, DetallePedido, Pago, Pedido, Producto


# ---------------------------------------------------------------- Catálogo
def home(request):
    productos = Producto.objects.filter(activo=True).select_related('categoria')
    categoria = None
    q = request.GET.get('q', '').strip()
    if request.GET.get('categoria'):
        categoria = get_object_or_404(Categoria, slug=request.GET['categoria'], activa=True)
        productos = productos.filter(categoria=categoria)
    if q:
        productos = productos.filter(Q(nombre__icontains=q) | Q(descripcion__icontains=q))
    for campo, filtro in (('precio_min', 'precio__gte'), ('precio_max', 'precio__lte')):
        try:
            if request.GET.get(campo):
                productos = productos.filter(**{filtro: Decimal(request.GET[campo])})
        except InvalidOperation:
            pass
    orden = request.GET.get('orden', '')
    productos = productos.order_by({'precio': 'precio', '-precio': '-precio', 'nuevos': '-creado'}.get(orden, 'nombre'))
    pagina = Paginator(productos, 12).get_page(request.GET.get('pagina'))
    params = request.GET.copy()
    params.pop('pagina', None)
    return render(request, 'tienda/catalogo.html', {
        'pagina': pagina, 'categoria_actual': categoria, 'q': q, 'orden': orden,
        'filtros_activos': bool(q or categoria or request.GET.get('precio_min') or request.GET.get('precio_max')),
        'querystring': params.urlencode(),
    })


def detalle_producto(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id, activo=True)
    relacionados = Producto.objects.filter(activo=True, categoria=producto.categoria).exclude(id=producto.id)[:3] \
        if producto.categoria else []
    return render(request, 'tienda/detalle_producto.html', {
        'producto': producto, 'form': AgregarCarritoForm(), 'relacionados': relacionados})


# ---------------------------------------------------------------- Carrito
@require_POST
def agregar_carrito(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id, activo=True)
    form = AgregarCarritoForm(request.POST)
    destino = request.POST.get('siguiente') or 'carrito'
    if not form.is_valid():
        messages.error(request, 'Revisa la cantidad indicada.')
        return redirect('producto', producto_id=producto.id)
    try:
        Carrito(request).agregar_item(producto, form.cleaned_data['cantidad'], form.cleaned_data['mensaje'])
        messages.success(request, f'Agregaste {producto.nombre} al carrito.')
    except StockInsuficiente as e:
        if e.disponible:
            messages.error(request, f'Solo quedan {e.disponible} unidades disponibles de {producto.nombre}.')
        else:
            messages.error(request, f'{producto.nombre} está agotado o ya tienes todas las unidades en tu carrito.')
        return redirect('producto', producto_id=producto.id)
    return redirect('home') if destino == 'home' else redirect('carrito')


def ver_carrito(request):
    carrito = Carrito(request)
    lineas = carrito.items()
    subtotal = sum((l['subtotal'] for l in lineas), Decimal('0'))
    envio = Decimal(settings.DELICIAS_LIAM['COSTO_ENVIO']) if lineas else Decimal('0')
    return render(request, 'tienda/carrito.html', {
        'lineas': lineas, 'subtotal': subtotal, 'envio': envio, 'total': subtotal + envio})


@require_POST
def actualizar_carrito(request):
    try:
        cantidad = int(request.POST.get('cantidad', 1))
        Carrito(request).actualizar_item(request.POST.get('clave', ''), cantidad)
    except ValueError:
        messages.error(request, 'Cantidad no válida.')
    except StockInsuficiente as e:
        messages.error(request, f'Solo hay {e.disponible} unidades disponibles de {e.producto.nombre}.')
    except Producto.DoesNotExist:
        pass
    return redirect('carrito')


@require_POST
def eliminar_carrito(request):
    Carrito(request).eliminar_item(request.POST.get('clave', ''))
    messages.info(request, 'Producto eliminado del carrito.')
    return redirect('carrito')


# ---------------------------------------------------------------- Cuentas
def registro(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = RegistroForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, f'¡Bienvenido(a), {user.first_name}! Tu cuenta fue creada.')
        return redirect(request.GET.get('next') or 'home')
    return render(request, 'registration/registro.html', {'form': form})


# ---------------------------------------------------------------- Compra
@login_required
def checkout(request):
    carrito = Carrito(request)
    lineas = carrito.items()
    if not lineas:
        messages.info(request, 'Tu carrito está vacío. Agrega productos antes de finalizar la compra.')
        return redirect('carrito')
    perfil = getattr(request.user, 'perfil', None)
    inicial = {
        'nombre_recibe': request.user.get_full_name(),
        'telefono_contacto': perfil.telefono if perfil else '',
        'fecha_entrega': timezone.localdate() + timedelta(days=1),
        'metodo_pago': Pago.TRANSFERENCIA,
        'direccion_guardada': request.user.direcciones.first(),
    }
    form = CheckoutForm(request.POST or None, usuario=request.user, initial=inicial)
    if request.method == 'POST' and form.is_valid():
        try:
            pedido = services.crear_pedido(request.user, carrito, form.datos_envio(), form.cleaned_data['metodo_pago'])
        except ValidationError as e:
            messages.error(request, ' '.join(e.messages) + ' Ajusta tu carrito para continuar.')
            return redirect('carrito')
        messages.success(request, f'Recibimos tu pedido #{pedido.id}.')
        return redirect('pedido', pedido_id=pedido.id)
    subtotal = sum((l['subtotal'] for l in lineas), Decimal('0'))
    envio = Decimal(settings.DELICIAS_LIAM['COSTO_ENVIO'])
    return render(request, 'tienda/checkout.html', {
        'form': form, 'lineas': lineas, 'subtotal': subtotal, 'envio': envio, 'total': subtotal + envio})


@login_required
def mis_pedidos(request):
    pedidos = request.user.pedidos.select_related('pago').prefetch_related('detalles')
    return render(request, 'tienda/mis_pedidos.html', {'pedidos': pedidos})


@login_required
def detalle_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido.objects.select_related('pago'), id=pedido_id, usuario=request.user)
    pago = getattr(pedido, 'pago', None)
    form = ComprobanteForm()
    if request.method == 'POST' and pago:
        form = ComprobanteForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                services.adjuntar_comprobante(pago, form.cleaned_data['comprobante'], form.cleaned_data['referencia'])
                messages.success(request, 'Recibimos tu comprobante. Te avisaremos cuando verifiquemos el pago.')
                return redirect('pedido', pedido_id=pedido.id)
            except ValidationError as e:
                messages.error(request, ' '.join(e.messages))
    pasos = ['Pendiente de pago', 'Pagado', 'En preparación', 'Enviado', 'Entregado']
    return render(request, 'tienda/detalle_pedido.html', {
        'pedido': pedido, 'pago': pago, 'form': form, 'pasos': pasos,
        'datos_transferencia': settings.DELICIAS_LIAM['DATOS_TRANSFERENCIA'],
        'horas_limite': settings.DELICIAS_LIAM['HORAS_LIMITE_PAGO'],
    })


@login_required
@require_POST
def cancelar_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id, usuario=request.user)
    try:
        services.cancelar_pedido(pedido, request.user)
        messages.success(request, f'El pedido #{pedido.id} fue cancelado.')
    except ValidationError as e:
        messages.error(request, ' '.join(e.messages))
    return redirect('pedido', pedido_id=pedido.id)


@login_required
def factura(request, pedido_id):
    filtro = {'id': pedido_id}
    if not request.user.is_staff:
        filtro['usuario'] = request.user
    pedido = get_object_or_404(Pedido, **filtro)
    response = HttpResponse(generar_pdf_factura(pedido), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="factura_{pedido.id}.pdf"'
    return response


# ---------------------------------------------------------------- Páginas legales
def politica_datos(request):
    return render(request, 'legal/politica_datos.html')


def terminos(request):
    return render(request, 'legal/terminos.html')


# ---------------------------------------------------------------- Panel interno
@staff_member_required
def panel(request):
    por_estado = dict(Pedido.objects.values_list('estado').annotate(n=Count('id')))
    return render(request, 'panel/panel.html', {
        'por_estado': [(v, etiqueta, por_estado.get(v, 0)) for v, etiqueta in Pedido.ESTADOS],
        'pagos_por_verificar': Pago.objects.filter(estado=Pago.EN_VERIFICACION).select_related('pedido__usuario'),
        'stock_bajo': Producto.objects.filter(activo=True, stock__lte=F('stock_minimo')).order_by('stock'),
        'pedidos_hoy': Pedido.objects.filter(fecha_entrega=timezone.localdate()).exclude(
            estado__in=[Pedido.CANCELADO, Pedido.ENTREGADO]),
    })


@permission_required('tienda.ver_reportes', raise_exception=True)
def reportes(request):
    hoy = timezone.localdate()
    form = FiltroReporteForm(request.GET or {'desde': hoy.replace(day=1), 'hasta': hoy})
    desde, hasta = hoy.replace(day=1), hoy
    if form.is_valid():
        desde, hasta = form.cleaned_data['desde'], form.cleaned_data['hasta']
    pedidos = Pedido.objects.filter(fecha__date__gte=desde, fecha__date__lte=hasta)
    validos = pedidos.exclude(estado__in=[Pedido.CANCELADO, Pedido.PENDIENTE_PAGO])
    resumen = validos.aggregate(total=Sum('total'), cantidad=Count('id'))
    resumen['ticket'] = (resumen['total'] / resumen['cantidad']) if resumen['cantidad'] else 0
    por_dia = validos.annotate(dia=TruncDate('fecha')).values('dia').annotate(
        total=Sum('total'), n=Count('id')).order_by('dia')
    top = DetallePedido.objects.filter(pedido__in=validos).values('producto__nombre').annotate(
        unidades=Sum('cantidad'), ventas=Sum(F('cantidad') * F('precio_unitario'))).order_by('-unidades')[:5]
    estados = dict(pedidos.values_list('estado').annotate(n=Count('id')))
    maximo = max([d['total'] for d in por_dia], default=0) or 1
    return render(request, 'panel/reportes.html', {
        'form': form, 'desde': desde, 'hasta': hasta, 'resumen': resumen,
        'por_dia': [dict(d, pct=int(d['total'] * 100 / maximo)) for d in por_dia], 'top': top,
        'estados': [(etiqueta, estados.get(v, 0)) for v, etiqueta in Pedido.ESTADOS],
    })
