from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls import url
from idgo_admin.views.account import AccountManager
from idgo_admin.views.account import delete_account
from idgo_admin.views.account import PasswordManager
from idgo_admin.views.account import ReferentAccountManager
from idgo_admin.views.account import SignIn
from idgo_admin.views.account import SignOut
from idgo_admin.views.account import SignUp
from idgo_admin.views.action import ActionsManager
from idgo_admin.views.dataset import all_datasets
from idgo_admin.views.dataset import DatasetManager
from idgo_admin.views.dataset import datasets
from idgo_admin.views.dataset import export
# from idgo_admin.views.dataset import ReferentDatasetManager
from idgo_admin.views.mailer import confirm_contribution
from idgo_admin.views.mailer import confirm_new_orga
from idgo_admin.views.mailer import confirm_rattachement
from idgo_admin.views.mailer import confirm_referent
from idgo_admin.views.mailer import confirmation_mail
from idgo_admin.views.mdedit import MDEdit
from idgo_admin.views.mdedit import MDEditTplEdit
from idgo_admin.views.organization import all_organisations
from idgo_admin.views.organization import CreateOrganisation
from idgo_admin.views.organization import organisation
from idgo_admin.views.organization import Subscription
from idgo_admin.views.organization import UpdateOrganisation
from idgo_admin.views.resource import ResourceManager
from idgo_admin.views.stuffs import DisplayLicenses


urlpatterns = [
    url('^$', datasets, name='datasets'),  # TODO: Home Page

    url('^signin/?$', SignIn.as_view(), name='signIn'),
    url('^signout/?$', SignOut.as_view(), name='signOut'),

    url('^signup/?$', SignUp.as_view(), name='sign_up'),

    url('^account/(?P<process>(update))/?$', AccountManager.as_view(), name='account_manager'),
    url('^deleteaccount/?$', delete_account, name='deleteAccount'),

    url('^dataset/?$', DatasetManager.as_view(), name='dataset'),
    url('^dataset/(?P<dataset_id>(\d+))/resources/?$', ResourceManager.as_view(), name='resource'),
    url('^dataset/(?P<dataset_id>(\d+))/mdedit/?$', MDEdit.as_view(), name='mdedit'),
    url('^dataset/(?P<dataset_id>(\d+))/mdedit/edit/?$', MDEditTplEdit.as_view(), name='mdedit_tpl_edit'),
    url('^dataset/mine/?$', datasets, name='datasets'),
    url('^dataset/all/?$', all_datasets, name='all_datasets'),
    url('^dataset/export/?$', export, name='export'),

    url('^member/all/?$', ReferentAccountManager.as_view(), name='all_members'),

    url('^organization/all/?$', all_organisations, name='all_organizations'),
    url('^organization/new/?$', CreateOrganisation.as_view(), name='create_organization'),
    url('^organization/(?P<id>(\d+))/?$', organisation, name='organization'),
    url('^organization/(?P<id>(\d+))/update/?$', UpdateOrganisation.as_view(), name='update_organization'),
    url('^organization/(?P<status>(member|contributor|referent))/(?P<subscription>(subscribe|unsubscribe))?$', Subscription.as_view(), name='subscription'),

    url('^password/(?P<process>(forget))/?$', PasswordManager.as_view(), name='password_manager'),
    url('^password/(?P<process>(initiate|reset))/(?P<key>(.+))/?$', PasswordManager.as_view(), name='password_manager'),

    url('^confirmation/email/(?P<key>.+)/?$', confirmation_mail, name='confirmation_mail'),
    url('^confirmation/createorganization/(?P<key>.+)/?$', confirm_new_orga, name='confirm_new_orga'),
    url('^confirmation/rattachment/(?P<key>.+)/?$', confirm_rattachement, name='confirm_rattachement'),
    url('^confirmation/contribute/(?P<key>.+)/?$', confirm_contribution, name='confirm_contribution'),
    url('^confirmation/referent/(?P<key>.+)/?$', confirm_referent, name='confirm_referent'),

    url('^action/$', ActionsManager.as_view(), name='action'),
    url('^licences/?$', DisplayLicenses.as_view(), name='licences')]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
