from django.conf.urls import url
from django.views.generic import TemplateView

from profiles.views import activation, delete_account, modify_account, \
                           sign_in, sign_out, sign_up


urlpatterns = [
    url(r'^/?$', TemplateView.as_view(
                            template_name='profiles/main.html'), name='main'),
    url(r'^signin/?$', sign_in, name='signIn'),
    url(r'^signout/?$', sign_out, name='signOut'),
    url(r'^signup/?$', sign_up, name='signUp'),
    url(r'^activate/(?P<key>.+)/?$', activation,  name='activation'),
    url(r'^modifyaccount/?$', modify_account, name='modifyAccount'),
    url(r'^deleteaccount/?$', delete_account, name='deleteAccount')
]
