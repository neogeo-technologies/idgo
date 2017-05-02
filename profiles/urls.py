from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^add_user$', views.add_user, name='add_user'),
    url(r'^update_user/([0-9]+)/$', views.update_user, name='update_user'),
    url(r'^register/$', views.register, name='register'),
    url(r'^activate/(?P<key>.+)$', views.activation,  name='activation'),
    url(r'^new-activation-link/(?P<user_id>\d+)/$', views.new_activation_link,  name='new_activation_link'),
]