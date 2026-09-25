from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import F
from django.urls import reverse
from django.utils.html import format_html

from . import services
from .models import (Categoria, DetallePedido, Direccion, HistorialEstado, MovimientoInventario, Pago,
                     Pedido, PerfilCliente, Producto)


def _cop(v):
    return '$ ' + f'{v:,.0f}'.replace(',', '.')


# ----------------------------------------------------------------- Catálogo
@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'orden', 'activa', 'num_productos')
    list_editable = ('orden', 'activa')
    prepopulated_fields = {'slug': ('nombre',)}
    search_fields = ('nombre',)

    @admin.display(description='Productos')
    def num_productos(self, obj):
        return obj.productos.count()


class StockBajoFilter(admin.SimpleListFilter):
    title = 'inventario'
    parameter_name = 'inventario'

    def lookups(self, request, model_admin):
        return [('bajo', 'Stock bajo'), ('agotado', 'Agotado')]

    def queryset(self, request, queryset):
        if self.value() == 'bajo':
            return queryset.filter(stock__gt=0, stock__lte=F('stock_minimo'))
        if self.value() == 'agotado':
            return queryset.filter(stock__lte=0)
        return queryset


class MovimientoInline(admin.TabularInline):
    model = MovimientoInventario
    extra = 0
    can_delete = False
    fields = ('fecha', 'tipo', 'cantidad', 'stock_resultante', 'motivo', 'usuario')
    readonly_fields = fields
    max_num = 0
    ordering = ('-fecha',)


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('miniatura', 'nombre', 'categoria', 'precio_cop', 'stock', 'estado_stock', 'activo')
    list_display_links = ('miniatura', 'nombre')
    list_filter = ('activo', 'categoria', StockBajoFilter, 'personalizable')
    list_editable = ('activo',)
    search_fields = ('nombre', 'descripcion')
    readonly_fields = ('stock', 'creado', 'actualizado')
    fieldsets = (
        (None, {'fields': ('nombre', 'categoria', 'descripcion', 'precio', 'imagen')}),
        ('Inventario', {'fields': ('stock', 'stock_minimo'),
                        'description': 'El stock se modifica registrando movimientos de inventario '
                                       '(al crear el producto puede indicar el stock inicial abajo).'}),
        ('Opciones', {'fields': ('personalizable', 'activo', 'creado', 'actualizado')}),
    )
    inlines = [MovimientoInline]
    actions = ['activar', 'desactivar']

    def get_readonly_fields(self, request, obj=None):
        # Al crear un producto se permite indicar el stock inicial
        return ('creado', 'actualizado') if obj is None else self.readonly_fields

    def save_model(self, request, obj, form, change):
        stock_inicial = obj.stock if not change else None
        if not change:
            obj.stock = 0
        super().save_model(request, obj, form, change)
        if stock_inicial:
            services.registrar_movimiento(obj, MovimientoInventario.ENTRADA, stock_inicial, request.user,
                                          'Stock inicial')

    @admin.display(description='')
    def miniatura(self, obj):
        if obj.imagen:
            return format_html('<img src="{}" style="height:40px;width:40px;object-fit:cover;border-radius:6px">',
                               obj.imagen.url)
        return '-'

    @admin.display(description='Precio', ordering='precio')
    def precio_cop(self, obj):
        return _cop(obj.precio)

    @admin.display(description='Estado')
    def estado_stock(self, obj):
        color = {'Disponible': '#2e7d32', 'Stock bajo': '#e65100', 'Agotado': '#c62828'}.get(obj.estado_inventario, '#666')
        return format_html('<strong style="color:{}">{}</strong>', color, obj.estado_inventario)

    @admin.action(description='Activar productos seleccionados')
    def activar(self, request, queryset):
        queryset.update(activo=True)

    @admin.action(description='Desactivar productos seleccionados')
    def desactivar(self, request, queryset):
        queryset.update(activo=False)


@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'producto', 'tipo', 'cantidad', 'stock_resultante', 'usuario', 'motivo')
    list_filter = ('tipo', 'producto__categoria')
    search_fields = ('producto__nombre', 'motivo')
    autocomplete_fields = ('producto',)
    fields = ('producto', 'tipo', 'cantidad', 'motivo')

    def has_change_permission(self, request, obj=None):
        return False  # los movimientos no se editan: se registra uno nuevo

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        try:
            mov = services.registrar_movimiento(obj.producto, obj.tipo, obj.cantidad, request.user, obj.motivo)
            obj.pk = mov.pk
        except ValidationError as e:
            messages.error(request, ' '.join(e.messages))


# ----------------------------------------------------------------- Pedidos
class DetalleInline(admin.TabularInline):
    model = DetallePedido
    extra = 0
    can_delete = False
    max_num = 0
    fields = ('producto', 'cantidad', 'precio_unitario', 'mensaje_personalizado')
    readonly_fields = fields


class HistorialInline(admin.TabularInline):
    model = HistorialEstado
    extra = 0
    can_delete = False
    max_num = 0
    fields = ('fecha', 'estado', 'usuario', 'comentario')
    readonly_fields = fields


def _accion_estado(nuevo, descripcion):
    def accion(modeladmin, request, queryset):
        ok = 0
        for pedido in queryset:
            try:
                services.cambiar_estado(pedido, nuevo, request.user, 'Actualizado desde el panel')
                ok += 1
            except ValidationError as e:
                modeladmin.message_user(request, f'Pedido #{pedido.id}: {" ".join(e.messages)}', messages.WARNING)
        if ok:
            modeladmin.message_user(request, f'{ok} pedido(s) actualizados a «{dict(Pedido.ESTADOS)[nuevo]}».')
    accion.__name__ = f'marcar_{nuevo.lower()}'
    accion.short_description = descripcion
    accion.allowed_permissions = ('change',)
    return accion


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('numero', 'fecha', 'cliente', 'total_cop', 'fecha_entrega', 'estado_badge', 'estado_pago', 'pdf')
    list_filter = ('estado', 'pago__metodo', 'pago__estado', 'fecha_entrega')
    search_fields = ('id', 'usuario__username', 'usuario__first_name', 'usuario__last_name', 'nombre_recibe')
    date_hierarchy = 'fecha'
    readonly_fields = ('usuario', 'estado', 'subtotal', 'costo_envio', 'total', 'fecha', 'actualizado')
    fieldsets = (
        (None, {'fields': ('usuario', 'estado', 'fecha', 'actualizado')}),
        ('Entrega', {'fields': ('nombre_recibe', 'telefono_contacto', 'direccion_entrega', 'fecha_entrega', 'notas')}),
        ('Valores', {'fields': ('subtotal', 'costo_envio', 'total')}),
    )
    inlines = [DetalleInline, HistorialInline]
    actions = [
        _accion_estado(Pedido.EN_PREPARACION, 'Marcar como «En preparación»'),
        _accion_estado(Pedido.ENVIADO, 'Marcar como «Enviado»'),
        _accion_estado(Pedido.ENTREGADO, 'Marcar como «Entregado»'),
        _accion_estado(Pedido.CANCELADO, 'Cancelar pedidos (libera el stock)'),
    ]

    def has_add_permission(self, request):
        return False  # los pedidos se crean desde la tienda

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    @admin.display(description='Pedido', ordering='id')
    def numero(self, obj):
        return f'#{obj.id}'

    @admin.display(description='Cliente', ordering='usuario__username')
    def cliente(self, obj):
        return obj.usuario.get_full_name() or obj.usuario.username

    @admin.display(description='Total', ordering='total')
    def total_cop(self, obj):
        return _cop(obj.total)

    @admin.display(description='Estado', ordering='estado')
    def estado_badge(self, obj):
        colores = {'PENDIENTE_PAGO': '#e65100', 'PAGADO': '#1565c0', 'EN_PREPARACION': '#6a1b9a',
                   'ENVIADO': '#00838f', 'ENTREGADO': '#2e7d32', 'CANCELADO': '#757575'}
        return format_html('<strong style="color:{}">{}</strong>', colores.get(obj.estado, '#000'),
                           obj.get_estado_display())

    @admin.display(description='Pago')
    def estado_pago(self, obj):
        pago = getattr(obj, 'pago', None)
        if not pago:
            return '-'
        url = reverse('admin:tienda_pago_change', args=[pago.id])
        return format_html('<a href="{}">{} · {}</a>', url, pago.get_metodo_display().split(' (')[0],
                           pago.get_estado_display())

    @admin.display(description='PDF')
    def pdf(self, obj):
        return format_html('<a href="{}">Descargar</a>', reverse('factura', args=[obj.id]))


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ('pedido', 'metodo', 'monto_cop', 'estado', 'ver_comprobante', 'fecha', 'fecha_verificacion')
    list_filter = ('estado', 'metodo')
    search_fields = ('pedido__id', 'referencia', 'pedido__usuario__username')
    readonly_fields = ('pedido', 'metodo', 'monto', 'estado', 'comprobante', 'referencia', 'fecha', 'fecha_verificacion')
    fields = readonly_fields + ('observacion',)
    actions = ['aprobar', 'rechazar']

    def has_add_permission(self, request):
        return False

    @admin.display(description='Monto')
    def monto_cop(self, obj):
        return _cop(obj.monto)

    @admin.display(description='Comprobante')
    def ver_comprobante(self, obj):
        return format_html('<a href="{}" target="_blank">Ver</a>', obj.comprobante.url) if obj.comprobante else '-'

    @admin.action(description='Aprobar pagos seleccionados', permissions=['change'])
    def aprobar(self, request, queryset):
        for pago in queryset.select_related('pedido'):
            try:
                services.aprobar_pago(pago, request.user)
                self.message_user(request, f'Pago del pedido #{pago.pedido_id} aprobado.')
            except ValidationError as e:
                self.message_user(request, f'Pedido #{pago.pedido_id}: {" ".join(e.messages)}', messages.WARNING)

    @admin.action(description='Rechazar pagos seleccionados', permissions=['change'])
    def rechazar(self, request, queryset):
        for pago in queryset.select_related('pedido'):
            try:
                services.rechazar_pago(pago, request.user)
                self.message_user(request, f'Pago del pedido #{pago.pedido_id} rechazado.', messages.WARNING)
            except ValidationError as e:
                self.message_user(request, f'Pedido #{pago.pedido_id}: {" ".join(e.messages)}', messages.WARNING)


# ----------------------------------------------------------------- Usuarios
class PerfilInline(admin.StackedInline):
    model = PerfilCliente
    can_delete = False
    extra = 0
    readonly_fields = ('acepta_tratamiento_datos', 'fecha_aceptacion')


class DireccionInline(admin.TabularInline):
    model = Direccion
    extra = 0


admin.site.unregister(User)


@admin.register(User)
class UsuarioAdmin(UserAdmin):
    inlines = [PerfilInline, DireccionInline]
    list_display = ('username', 'first_name', 'last_name', 'email', 'is_staff', 'grupos')
    list_filter = ('is_staff', 'groups', 'is_active')

    @admin.display(description='Roles')
    def grupos(self, obj):
        return ', '.join(g.name for g in obj.groups.all()) or '-'
