from django.conf.urls import url
from idgo_admin.views.dataset import DatasetManager
from idgo_admin.views.profile import activation_admin
from idgo_admin.views.profile import confirmation_email
from idgo_admin.views.profile import Contributions
from idgo_admin.views.profile import delete_account
from idgo_admin.views.profile import forgotten_password
from idgo_admin.views.profile import home
from idgo_admin.views.profile import modify_account
from idgo_admin.views.profile import publish_request
from idgo_admin.views.profile import publish_request_confirme
from idgo_admin.views.profile import reset_password
# from idgo_admin.views.profile import sign_in
from idgo_admin.views.profile import SignIn
from idgo_admin.views.profile import sign_out
from idgo_admin.views.profile import sign_up
from idgo_admin.views.resource import ResourceManager


urlpatterns = [
    url('^dataset/?$', DatasetManager.as_view(), name='dataset'),
    url('^(?P<dataset_id>(\d+))/resources/?$', ResourceManager.as_view(),
        name='resource'),
    url('^$', home, name='home'),
    url('^signin/?$', SignIn.as_view(), name='signIn'),
    url('^signout/?$', sign_out, name='signOut'),
    url('^signup/?$', sign_up, name='signUp'),
    url('^forgotten_password/?$', forgotten_password, name='forgottenPassword'),
    url('^reset_password/(?P<key>.+)/?$', reset_password, name='resetPassword'),
    url('^confirmation_email/(?P<key>.+)/?$',
        confirmation_email, name='confirmation_mail'),
    url('^activation_admin/(?P<key>.+)/?$',
        activation_admin, name='activation_admin'),
    url('^modifyaccount/?$', modify_account, name='modifyAccount'),
    url('^publish_request/(?P<key>.+)/?$',
        publish_request_confirme, name='publish_request_confirme'),
    url('^publish_request/?$', publish_request, name='publish_request'),
    url('^contributions/?$', Contributions.as_view(), name='contributions'),
    url('^deleteaccount/?$', delete_account, name='deleteAccount')]
