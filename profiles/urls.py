from django.conf.urls import url
from profiles.views import activation_admin
from profiles.views import confirmation_email
from profiles.views import contributions
from profiles.views import delete_account
from profiles.views import home
from profiles.views import modify_account
from profiles.views import publish_request
from profiles.views import publish_request_confirme
from profiles.views import sign_in
from profiles.views import sign_out
from profiles.views import sign_up


urlpatterns = [
    url('^$', home, name='home'),
    url('^signin/?$', sign_in, name='signIn'),
    url('^signout/?$', sign_out, name='signOut'),
    url('^signup/?$', sign_up, name='signUp'),
    url('^confirmation_email/(?P<key>.+)/?$',
        confirmation_email, name='confirmation_mail'),
    url('^activation_admin/(?P<key>.+)/?$',
        activation_admin, name='activation_admin'),
    url('^modifyaccount/?$', modify_account, name='modifyAccount'),
    url('^publish_request/(?P<key>.+)/?$',
        publish_request_confirme, name='publish_request_confirme'),
    url('^publish_request/?$', publish_request, name='publish_request'),
    url('^contributions/?$', contributions, name='contributions'),
    url('^deleteaccount/?$', delete_account, name='deleteAccount')]
