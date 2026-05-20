from django.shortcuts import redirect, render
from .models import Producto, Pedido
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# Vista de home

def home(request):
    productos = Producto.objects.all()
    return render(request, 'home.html', {'productos': productos})


# Carrito de compras

def agregar_carrito(request, producto_id):
    carrito = request.session.get('carrito', {})

    producto_id = str(producto_id)

    if producto_id in carrito:
        carrito[producto_id] += 1
    else:
        carrito[producto_id] = 1

    request.session['carrito'] = carrito
    return redirect('home')

def ver_carrito(request):
    carrito = request.session.get('carrito', {})
    productos = []
    total = 0

    for key, cantidad in carrito.items():
        producto = Producto.objects.get(id=key)
        subtotal = producto.precio * cantidad
        total += subtotal

        productos.append({
            'producto': producto,
            'cantidad': cantidad,
            'subtotal': subtotal,
        })
    
    return render(request, 'carrito.html', {'productos': productos, 'total': total})
    
def eliminar_carrito(request, producto_id):
    carrito = request.session.get('carrito', {})
    producto_id = str(producto_id)

    if producto_id in carrito:
        del carrito[producto_id]
        request.session['carrito'] = carrito

    return redirect('carrito')

# Vista de login y registro

def registro(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = UserCreationForm()
    
    return render(request, 'registro.html', {'form': form})

# Vista de checkput

@login_required
def finalizar_compra(request):
    carrito = request.session.get('carrito', {})
    total = 0

    for key, cantidad in carrito.items():
        producto = Producto.objects.get(id=key)
        total += producto.precio * cantidad

    Pedido.objects.create(usuario=request.user, total=total)

    request.session['carrito'] = {}
    
    return render(request, 'compra_exitosa.html')

# Vista de pedidos

@login_required
def mis_pedidos(request):
    pedidos=Pedido.objects.filter(usuario=request.user).order_by('-fecha')
    return render(request, 'mis_pedidos.html',{'pedidos':pedidos})

# Generacion factura PDF

def generar_factura(request, pedido_id):

    pedido = Pedido.objects.get(id=pedido_id)
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="factura_{pedido.id}.pdf"'
   
    pdf = canvas.Canvas(response, pagesize=letter)
   
    pdf.setTitle("Factura Delicias Liam")
 
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(180, 750, "DELICIAS LIAM")
    
    pdf.setFont("Helvetica", 12)

    pdf.drawString(50, 700, f"Factura #: {pedido.id}")
    pdf.drawString(50, 680, f"Cliente: {pedido.usuario.username}")
    pdf.drawString(50, 660, f"Fecha: {pedido.fecha.strftime('%d/%m/%Y %H:%M')}")
    pdf.drawString(50, 640, f"Estado: {pedido.estado}")
  
    pdf.line(50, 620, 550, 620)

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, 590, f"TOTAL PAGADO: $ {pedido.total}")

    pdf.setFont("Helvetica", 11)
    pdf.drawString(50, 540, "Gracias por comprar en Delicias Liam")

    pdf.save()

    return response