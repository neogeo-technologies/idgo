# Copyright (c) 2017-2018 Datasud.
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.


from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls import url
from idgo_admin.views.account import delete_account
from idgo_admin.views.account import PasswordManager
from idgo_admin.views.account import ReferentAccountManager
from idgo_admin.views.account import SignIn
from idgo_admin.views.account import SignOut
from idgo_admin.views.account import SignUp
from idgo_admin.views.account import UpdateAccount
from idgo_admin.views.action import ActionsManager
from idgo_admin.views.dataset import all_datasets
from idgo_admin.views.dataset import DatasetManager
from idgo_admin.views.dataset import my_datasets
from idgo_admin.views.export import export
from idgo_admin.views.mailer import confirm_contribution
from idgo_admin.views.mailer import confirm_new_orga
from idgo_admin.views.mailer import confirm_rattachement
from idgo_admin.views.mailer import confirm_referent
from idgo_admin.views.mailer import confirmation_mail
from idgo_admin.views.mdedit import DatasetMDEdit
from idgo_admin.views.mdedit import DatasetMDEditTplEdit
from idgo_admin.views.mdedit import ServiceMDEdit
from idgo_admin.views.mdedit import ServiceMDEditTplEdit
from idgo_admin.views.organization import all_organisations
from idgo_admin.views.organization import CreateOrganisation
from idgo_admin.views.organization import organisation
from idgo_admin.views.organization import OrganisationOWS
from idgo_admin.views.organization import OrganisationOWSMDedit
from idgo_admin.views.organization import Subscription
from idgo_admin.views.organization import UpdateOrganisation
from idgo_admin.views.resource import LayerManager
from idgo_admin.views.resource import ResourceManager
from idgo_admin.views.stuffs import DisplayLicenses
from idgo_admin.views.stuffs import ows_preview


urlpatterns = [
    url('^$', my_datasets, name='datasets'),  # TODO: Home Page

    url('^signin/?$', SignIn.as_view(), name='signIn'),
    url('^signout/?$', SignOut.as_view(), name='signOut'),

    url('^account/create/?$', SignUp.as_view(), name='sign_up'),
    url('^account/update/?$', UpdateAccount.as_view(), name='update_account'),
    url('^account/delete/?$', delete_account, name='deleteAccount'),

    url('^dataset/?$', DatasetManager.as_view(), name='dataset'),
    url('^dataset/(?P<dataset_id>(\d+))/resource/?$', ResourceManager.as_view(), name='resource'),
    url('^dataset/(?P<dataset_id>(\d+))/resource/(?P<resource_id>(\d+))/layer/(?P<layer_id>([a-z0-9_]*))$', LayerManager.as_view(), name='layer'),

    url('^dataset/(?P<dataset_id>(\d+))/mdedit/?$', DatasetMDEdit.as_view(), name='mdedit'),
    url('^dataset/(?P<dataset_id>(\d+))/mdedit/edit/?$', DatasetMDEditTplEdit.as_view(), name='mdedit_tpl_edit'),
    url('^dataset/mine/?$', my_datasets, name='datasets'),
    url('^dataset/all/?$', all_datasets, name='all_datasets'),
    url('^dataset/export/?$', export, name='export'),

    url('^member/all/?$', ReferentAccountManager.as_view(), name='all_members'),

    url('^organisation/all/?$', all_organisations, name='all_organizations'),
    url('^organisation/new/?$', CreateOrganisation.as_view(), name='create_organization'),

    url('^organisation/ows/?$', OrganisationOWS.as_view(), name='organization_ows'),
    url('^organisation/ows/mdedit?$', OrganisationOWSMDedit.as_view(), name='organization_ows_mdedit'),
    url('^organisation/(?P<id>(\d+))/?$', organisation, name='organization'),

    url('^md/service/(?P<id>(\d+))/mdedit/edit/?$', ServiceMDEdit.as_view(), name='service_mdedit'),
    url('^md/service/(?P<id>(\d+))/mdedit/edit/?$', ServiceMDEditTplEdit.as_view(), name='service_mdedit_tpl_edit'),

    url('^organisation/(?P<id>(\d+))/update/?$', UpdateOrganisation.as_view(), name='update_organization'),
    url('^organisation/(?P<status>(member|contributor|referent))/(?P<subscription>(subscribe|unsubscribe))?$', Subscription.as_view(), name='subscription'),

    url('^password/(?P<process>(forget))/?$', PasswordManager.as_view(), name='password_manager'),
    url('^password/(?P<process>(initiate|reset))/(?P<key>(.+))/?$', PasswordManager.as_view(), name='password_manager'),

    url('^confirmation/email/(?P<key>.+)/?$', confirmation_mail, name='confirmation_mail'),
    url('^confirmation/createorganization/(?P<key>.+)/?$', confirm_new_orga, name='confirm_new_orga'),
    url('^confirmation/rattachment/(?P<key>.+)/?$', confirm_rattachement, name='confirm_rattachement'),
    url('^confirmation/contribute/(?P<key>.+)/?$', confirm_contribution, name='confirm_contribution'),
    url('^confirmation/referent/(?P<key>.+)/?$', confirm_referent, name='confirm_referent'),

    url('^action/$', ActionsManager.as_view(), name='action'),
    url('^licences/?$', DisplayLicenses.as_view(), name='licences'),

    url('^owspreview/$', ows_preview, name='ows_preview')]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
