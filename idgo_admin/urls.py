from django.conf.urls import url
from idgo_admin.views.account import AccountManager
from idgo_admin.views.account import delete_account
from idgo_admin.views.account import forgotten_password
# from idgo_admin.views.account import modify_account
from idgo_admin.views.account import reset_password
# from idgo_admin.views.account import sign_up
from idgo_admin.views.account import SignIn
from idgo_admin.views.account import SignOut
from idgo_admin.views.dataset import DatasetManager
from idgo_admin.views.dataset import datasets
from idgo_admin.views.mailer import confirm_contribution
from idgo_admin.views.mailer import confirm_new_orga
from idgo_admin.views.mailer import confirm_rattachement
from idgo_admin.views.mailer import confirm_referent
from idgo_admin.views.mailer import confirmation_mail
from idgo_admin.views.mdedit import get_list_xml
from idgo_admin.views.mdedit import get_url
from idgo_admin.views.mdedit import get_xml
from idgo_admin.views.mdedit import MDEdit
from idgo_admin.views.mdedit import MDEditTplEdit
from idgo_admin.views.mdedit import send_xml
from idgo_admin.views.organization_handler import contribution_request
from idgo_admin.views.organization_handler import Contributions
# from idgo_admin.views.organization_handler import Referents
from idgo_admin.views.resource import ResourceManager
from idgo_admin.views.stuffs import DisplayLicenses


urlpatterns = [
    url('^dataset/?$', DatasetManager.as_view(), name='dataset'),
    url('^dataset/(?P<dataset_id>(\d+))/resources/?$', ResourceManager.as_view(), name='resource'),
    url('^dataset/(?P<dataset_id>(\d+))/mdedit/?$', MDEdit.as_view(), name='mdedit'),
    url('^dataset/(?P<dataset_id>(\d+))/mdedit/geturl/?$', get_url, name='mdedit_get_url'),
    url('^dataset/(?P<dataset_id>(\d+))/mdedit/getxml/?$', get_xml, name='mdedit_get_xml'),
    url('^dataset/(?P<dataset_id>(\d+))/mdedit/sendxml/?$', send_xml, name='mdedit_send_xml'),
    url('^dataset/(?P<dataset_id>(\d+))/mdedit/getlistxml/?$', get_list_xml, name='mdedit_get_list_xml'),
    url('^dataset/(?P<dataset_id>(\d+))/mdedit/edit/?$', MDEditTplEdit.as_view(), name='mdedit_tpl_edit'),
    url('^$', datasets, name='home'),
    url('^signin/?$', SignIn.as_view(), name='signIn'),
    url('^signout/?$', SignOut.as_view(), name='signOut'),
    # url('^signup/?$', sign_up, name='signUp'),
    url('^account/(?P<process>(create|update))/?$', AccountManager.as_view(), name='account_manager'),
    url('^forgottenpassword/?$', forgotten_password, name='forgottenPassword'),
    url('^resetpassword/(?P<key>.+)/?$', reset_password, name='resetPassword'),
    url('^confirmation/email/(?P<key>.+)/?$', confirmation_mail, name='confirmation_mail'),
    url('^confirmation/createorganization/(?P<key>.+)/?$', confirm_new_orga, name='confirm_new_orga'),
    url('^confirmation/rattachment/(?P<key>.+)/?$', confirm_rattachement, name='confirm_rattachement'),
    url('^confirmation/referent/(?P<key>.+)/?$', confirm_referent, name='confirm_referent'),
    url('^confirmation/contribute/(?P<key>.+)/?$', confirm_contribution, name='confirm_contribution'),
    # url('^modifyaccount/?$', modify_account, name='modifyAccount'),
    # url('^activation_admin/(?P<key>.+)/?$', activation_admin, name='activation_admin'),
    url('^organizations/contribute/(?P<key>.+)/?$', contribution_request, name='contribute'),
    url('^organizations/contribute/?$', contribution_request, name='contribute'),
    url('^organizations/?$', Contributions.as_view(), name='organizations'),
    url('^licences/?$', DisplayLicenses.as_view(), name='licences'),
    url('^deleteaccount/?$', delete_account, name='deleteAccount')]
