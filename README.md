# Procédure d'installation

## Mise en place de l'environnement

```shell
~> sudo apt-get install binutils libproj-dev gdal-bin python-gdal build-essential autoconf libtool
~> sudo apt-get install libsasl2-dev python-dev libldap2-dev libssl-dev python3-dev python3-venv
~> mkdir idgo_venv
~> cd idgo_venv
~/idgo_venv> virtualenv -p python3.5 .
~/idgo_venv> source bin/activate
(idgo_venv) ~/idgo_venv> pip install captcha
(idgo_venv) ~/idgo_venv> pip install passlib
(idgo_venv) ~/idgo_venv> pip install ckanapi
(idgo_venv) ~/idgo_venv> pip install requests
(idgo_venv) ~/idgo_venv> pip install psycopg2
(idgo_venv) ~/idgo_venv> pip install django==1.11
(idgo_venv) ~/idgo_venv> pip install django-taggit
(idgo_venv) ~/idgo_venv> pip install django-bootstrap3
(idgo_venv) ~/idgo_venv> pip install django-mama-cas
(idgo_venv) ~/idgo_venv> pip install timeout-decorator
```

## Lancement projet dans dossier courant

```shell
(idgo_venv) idgo_venv> django-admin startproject idgo_project
(idgo_venv) idgo_venv> cd idgo_project/p
```

### `settings.py`

``` python
"""
Modèle du fichier `setting.py` pour le projet IDGO.

"""


import logging
import os


# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'abcdefghijklmnopqrstuvwxyz0123456789'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['127.0.0.1', 'localhost']

DOMAIN_NAME = '127.0.0.1:8000'

CKAN_URL = 'http://hostname'
CKAN_API_KEY = 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'

GEONETWORK_URL = ''
GEONETWORK_LOGIN = ''
GEONETWORK_PASSWORD = ''

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',
    'mama_cas',
    'taggit',
    'bootstrap3',
    'idgo_admin']

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware']

ROOT_URLCONF = 'idgo_project.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.debug',
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages']}}]

WSGI_APPLICATION = 'idgo_project.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'idgo_admin',
        'USER': '',
        'HOST': '',
        'PORT': '5432'}}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'}]

AUTHENTICATION_BACKENDS = ('django.contrib.auth.backends.ModelBackend',)

MAMA_CAS_SERVICES = [
    {
        'SERVICE': '',
        'CALLBACKS': [
            'mama_cas.callbacks.user_name_attributes',
            'mama_cas.callbacks.user_model_attributes'
        ],
        'LOGOUT_ALLOW': True,
        'LOGOUT_URL': ''
    },
]

LANGUAGE_CODE = 'FR-fr'

SESSION_EXPIRE_AT_BROWSER_CLOSE = True

SESSION_COOKIE_AGE = 3600

TIME_ZONE = 'Europe/Paris'

USE_I18N = True

USE_L10N = True

USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static')]

MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = ''
EMAIL_HOST_USER = ''
EMAIL_HOST_PASSWORD = ''
EMAIL_PORT = 587
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = ''

ADMIN_EMAIL = ''

LOGIN_URL = 'idgo_admin:signIn'

```

### `urls.py`

``` python
from django.conf.urls import include
from django.conf.urls import url
from django.contrib import admin


urlpatterns = [
    url('^', include('idgo_admin.urls', namespace='idgo_admin')),
    url('^admin/', admin.site.urls),
    url(r'', include('mama_cas.urls'))]

```

## Création du super utilisateur CKAN


## Charger les lexiques de données en base

``` shell
~> cd idgo_venv
~/idgo_venv> source bin/activate
(idgo_venv) ~/idgo_venv> python manage.py loaddata data.json
```
