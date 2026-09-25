from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.utils import timezone

from .models import Direccion, Pago, PerfilCliente

telefono_validator = RegexValidator(r'^\+?\d{7,15}$', 'Escribe solo números (7 a 15 dígitos).')


class EstiloBootstrap:
    """Agrega las clases de Bootstrap a los campos del formulario."""

    def _aplicar_estilo(self):
        for campo in self.fields.values():
            w = campo.widget
            if isinstance(w, forms.CheckboxInput):
                w.attrs.setdefault('class', 'form-check-input')
            elif isinstance(w, forms.RadioSelect):
                w.attrs.setdefault('class', 'form-check-input')
            elif isinstance(w, forms.Select):
                w.attrs.setdefault('class', 'form-select')
            else:
                w.attrs.setdefault('class', 'form-control')


class RegistroForm(EstiloBootstrap, UserCreationForm):
    first_name = forms.CharField(label='Nombre', max_length=150)
    last_name = forms.CharField(label='Apellidos', max_length=150)
    email = forms.EmailField(label='Correo electrónico')
    telefono = forms.CharField(label='Celular', max_length=20, validators=[telefono_validator])
    acepta_tratamiento_datos = forms.BooleanField(
        label='Autorizo el tratamiento de mis datos personales según la política de Delicias Liam',
        error_messages={'required': 'Debes aceptar la política de tratamiento de datos para crear tu cuenta.'})

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')
        labels = {'username': 'Usuario'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._aplicar_estilo()

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Ya existe una cuenta con este correo.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            PerfilCliente.objects.update_or_create(usuario=user, defaults={
                'telefono': self.cleaned_data['telefono'],
                'acepta_tratamiento_datos': True,
                'fecha_aceptacion': timezone.now(),
            })
        return user


class AgregarCarritoForm(forms.Form):
    cantidad = forms.IntegerField(min_value=1, max_value=50, initial=1)
    mensaje = forms.CharField(label='Mensaje para la tarjeta', max_length=200, required=False,
                              widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Ej.: ¡Feliz cumpleaños, mamá!'}))


class CheckoutForm(EstiloBootstrap, forms.Form):
    direccion_guardada = forms.ModelChoiceField(queryset=Direccion.objects.none(), required=False,
                                                empty_label='Usar una dirección nueva', label='Dirección')
    direccion = forms.CharField(label='Dirección', max_length=150, required=False)
    barrio = forms.CharField(max_length=80, required=False)
    ciudad = forms.CharField(max_length=60, initial='Bogotá', required=False)
    indicaciones = forms.CharField(max_length=200, required=False,
                                   help_text='Torre, apartamento, punto de referencia…')
    guardar_direccion = forms.BooleanField(label='Guardar esta dirección para próximas compras',
                                           required=False, initial=True)
    nombre_recibe = forms.CharField(label='Nombre de quien recibe', max_length=120)
    telefono_contacto = forms.CharField(label='Celular de contacto', max_length=20, validators=[telefono_validator])
    fecha_entrega = forms.DateField(label='Fecha de entrega deseada',
                                    widget=forms.DateInput(attrs={'type': 'date'}))
    metodo_pago = forms.ChoiceField(label='Método de pago', choices=Pago.METODOS, widget=forms.RadioSelect)
    notas = forms.CharField(label='Notas para el pedido', max_length=300, required=False,
                            widget=forms.Textarea(attrs={'rows': 2}))

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        self._aplicar_estilo()
        if usuario is not None:
            self.fields['direccion_guardada'].queryset = usuario.direcciones.all()

    def clean_fecha_entrega(self):
        fecha = self.cleaned_data['fecha_entrega']
        if fecha < timezone.localdate():
            raise forms.ValidationError('La fecha de entrega no puede ser anterior a hoy.')
        return fecha

    def clean(self):
        datos = super().clean()
        if not datos.get('direccion_guardada'):
            if not datos.get('direccion'):
                self.add_error('direccion', 'Escribe la dirección de entrega o elige una guardada.')
            if not datos.get('ciudad'):
                self.add_error('ciudad', 'Indica la ciudad.')
        return datos

    def datos_envio(self):
        """Datos de entrega que se copian al pedido. Guarda la dirección si se pidió."""
        d = self.cleaned_data
        direccion = d.get('direccion_guardada')
        if direccion is None:
            direccion = Direccion(usuario=self.usuario, direccion=d['direccion'], barrio=d.get('barrio', ''),
                                  ciudad=d.get('ciudad') or 'Bogotá', indicaciones=d.get('indicaciones', ''))
            if d.get('guardar_direccion'):
                direccion.save()
        texto = str(direccion) + (f' ({direccion.indicaciones})' if direccion.indicaciones else '')
        return {
            'nombre_recibe': d['nombre_recibe'],
            'telefono_contacto': d['telefono_contacto'],
            'direccion_entrega': texto,
            'fecha_entrega': d['fecha_entrega'],
            'notas': d.get('notas', ''),
        }


class ComprobanteForm(forms.Form):
    comprobante = forms.FileField(label='Comprobante de pago (imagen o PDF)')
    referencia = forms.CharField(label='Número de referencia (opcional)', max_length=60, required=False)

    def clean_comprobante(self):
        archivo = self.cleaned_data['comprobante']
        nombre = archivo.name.lower()
        if not nombre.endswith(('.jpg', '.jpeg', '.png', '.webp', '.pdf')):
            raise forms.ValidationError('Sube una imagen (JPG, PNG o WEBP) o un PDF.')
        if archivo.size > 5 * 1024 * 1024:
            raise forms.ValidationError('El archivo no puede superar 5 MB.')
        return archivo


class FiltroReporteForm(forms.Form):
    desde = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    hasta = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
