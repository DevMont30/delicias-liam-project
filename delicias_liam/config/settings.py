"""
Configuración de Django para el proyecto Delicias Liam.

Los valores sensibles (clave secreta, modo depuración, base de datos) se leen de
variables de entorno para no publicarlos en el repositorio. Si no se definen, se
usan valores de desarrollo (SQLite y DEBUG activo).
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(nombre, defecto=False):
    return os.environ.get(nombre, str(defecto)).lower() in ('1', 'true', 'si', 'sí', 'yes')


# --- Seguridad -------------------------------------------------------------
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'solo-para-desarrollo-cambie-esta-clave-en-produccion',
)
DEBUG = env_bool('DJANGO_DEBUG', True)
ALLOWED_HOSTS = [h for h in os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if h]

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = env_bool('DJANGO_SSL_REDIRECT', True)
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# --- Aplicaciones ----------------------------------------------------------
INSTALLED_APPS = [
    # 'tienda' va primero para que sus plantillas (p. ej. recuperación de contraseña)
    # tengan prioridad sobre las del administrador de Django.
    'tienda.apps.TiendaConfig',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'tienda.context_processors.tienda',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# --- Base de datos ---------------------------------------------------------
# Por defecto SQLite (desarrollo). Para usar MySQL defina DB_ENGINE=mysql y las
# variables DB_NAME, DB_USER, DB_PASSWORD, DB_HOST y DB_PORT, e instale el
# conector con: pip install mysqlclient
if os.environ.get('DB_ENGINE', 'sqlite').lower() == 'mysql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.environ.get('DB_NAME', 'delicias_liam'),
            'USER': os.environ.get('DB_USER', 'root'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '3306'),
            'OPTIONS': {'charset': 'utf8mb4'},
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- Contraseñas -----------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# --- Idioma y zona horaria -------------------------------------------------
LANGUAGE_CODE = 'es-co'
TIME_ZONE = 'America/Bogota'
USE_I18N = True
USE_TZ = True

# --- Archivos estáticos y de medios ----------------------------------------
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# --- Autenticación ---------------------------------------------------------
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# Correo: en desarrollo los correos (p. ej. recuperación de contraseña) se
# imprimen en la consola. En producción configure un servidor SMTP.
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'Delicias Liam <no-responder@deliciasliam.co>')

# --- Parámetros del negocio ------------------------------------------------
# COMPLETAR con los datos reales de Delicias Liam.
DELICIAS_LIAM = {
    'WHATSAPP': os.environ.get('DL_WHATSAPP', ''),          # ej.: 573001234567 (sin + ni espacios)
    'INSTAGRAM': os.environ.get('DL_INSTAGRAM', ''),        # ej.: https://www.instagram.com/deliciasliam
    'DATOS_TRANSFERENCIA': os.environ.get(
        'DL_DATOS_TRANSFERENCIA',
        'COMPLETAR: entidad, tipo y número de cuenta (o Nequi/Daviplata) y titular.',
    ),
    'COSTO_ENVIO': int(os.environ.get('DL_COSTO_ENVIO', '0')),
    'HORAS_LIMITE_PAGO': int(os.environ.get('DL_HORAS_LIMITE_PAGO', '48')),
}
