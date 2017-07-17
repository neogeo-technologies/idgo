from django.conf.urls import url
from .views.dataset import DatasetManager
from .views.resource import ResourceManager
from .views.profile import activation_admin
from .views.profile import confirmation_email
from .views.profile import contributions
from .views.profile import delete_account
from .views.profile import home
from .views.profile import modify_account
from .views.profile import publish_delete
from .views.profile import publish_request
from .views.profile import publish_request_confirme
from .views.profile import sign_in
from .views.profile import sign_out
from .views.profile import sign_up


urlpatterns = [
    url('^dataset/?$', DatasetManager.as_view(), name='dataset'),
    url('^(?P<dataset_id>(\d+))/resources/?$', ResourceManager.as_view(),
        name='resource'),
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
    url('^publish_delete/?$', publish_delete, name='publish_delete'),
    url('^contributions/?$', contributions, name='contributions'),
    url('^deleteaccount/?$', delete_account, name='deleteAccount')]
