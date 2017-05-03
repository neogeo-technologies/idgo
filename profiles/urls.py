from django.conf.urls import url

from profiles.views import (add_user, update_user, register,
                            activation, new_activation_link, UpdateUserData)


urlpatterns = [
    url(r'^add_user/?$', add_user, name='add_user'),
    url(r'^update_user/([0-9]+)/?$', update_user, name='update_user'),
    url(r'^register/?$', register, name='register'),
    url(r'^activate/(?P<key>.+)/?$', activation,  name='activation'),
    url(r'^new-activation-link/(?P<user_id>\d+)/$', new_activation_link,  name='new_activation_link'),
]