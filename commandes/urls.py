from django.conf.urls import include, url
from . import views

urlpatterns = [
    url('^commandes/?', views.upload_file, name='index')
    ]
