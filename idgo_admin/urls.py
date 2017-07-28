from django.conf.urls import url
from idgo_admin.views.dataset import DatasetManager
from idgo_admin.views.dataset import DisplayLicenses
# from idgo_admin.views.profile import activation_admin
from idgo_admin.views.profile import confirmation_mail
from idgo_admin.views.profile import confirm_new_orga
from idgo_admin.views.profile import confirm_rattachement
from idgo_admin.views.profile import confirm_referent
from idgo_admin.views.profile import confirm_contribution
from idgo_admin.views.profile import contribution_request
from idgo_admin.views.profile import Contributions
from idgo_admin.views.profile import delete_account
from idgo_admin.views.profile import forgotten_password
from idgo_admin.views.profile import home
from idgo_admin.views.profile import modify_account
# from idgo_admin.views.profile import publish_request
# from idgo_admin.views.profile import publish_request_confirme
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
    url('^confirmation_mail/(?P<key>.+)/?$',
        confirmation_mail, name='confirmation_mail'),
    url('^confirm_new_orga/(?P<key>.+)/?$',
        confirm_new_orga, name='confirm_new_orga'),
    url('^confirm_rattachement/(?P<key>.+)/?$',
        confirm_rattachement, name='confirm_rattachement'),
    url('^confirm_referent/(?P<key>.+)/?$',
        confirm_referent, name='confirm_referent'),
    url('^confirm_contribution/(?P<key>.+)/?$',
        confirm_contribution, name='confirm_contribution'),
    url('^modifyaccount/?$', modify_account, name='modifyAccount'),
    # url('^activation_admin/(?P<key>.+)/?$',
    #     activation_admin, name='activation_admin'),
    url('^contribution_request/(?P<key>.+)/?$',
        contribution_request, name='contribution_request'),
    url('^contribution_request/?$', contribution_request, name='contribution_request'),
    url('^contributions/?$', Contributions.as_view(), name='contributions'),
    url('^licences/?$', DisplayLicenses.as_view(), name='licences'),
    url('^deleteaccount/?$', delete_account, name='deleteAccount')]
