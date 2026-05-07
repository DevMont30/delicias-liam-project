from django.shortcuts import redirect, render
from .models import Producto, Pedido
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required

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

@login_required
def mis_pedidos(request):
    pedidos=Pedido.objects.filter(usuario=request.user).order_by('-fecha')
    return render(request, 'mis_pedidos.html',{'pedidos':pedidos})