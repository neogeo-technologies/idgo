from django.conf.urls import url

from api.views import DatasetList as APIDatasetList
from api.views import DatasetShow as APIDatasetShow
from api.views import OrganisationList as APIOrganisationList
from api.views import OrganisationShow as APIOrganisationShow
from api.views import ResourceList as APIResourceList
from api.views import ResourceShow as APIResourceShow
from api.views import UserList as APIUserList
from api.views import UserShow as APIUserShow


urlpatterns = [

    url('^user/?$', APIUserList.as_view(), name='user_list'),

    url('^user/(?P<username>\w+)/?$', APIUserShow.as_view(), name='user_show'),

    url('^organisation/?$', APIOrganisationList.as_view(), name='organisation_list'),

    url(
        '^organisation/(?P<organisation_name>[a-z0-9\\-]+)/?$',
        APIOrganisationShow.as_view(), name='organisation_show'
    ),

    url('^dataset/?$', APIDatasetList.as_view(), name='dataset_list'),

    url(
        '^dataset/(?P<dataset_name>[a-z0-9\\-]+)/?$',
        APIDatasetShow.as_view(), name='dataset_show'
    ),

    url(
        '^dataset/(?P<dataset_name>[a-z0-9\\-]+)/resource/?$',
        APIResourceList.as_view(), name='resource_list'
    ),

    url(
        '^dataset/(?P<dataset_name>[a-z0-9\\-]+)/resource/(?P<resource_id>[a-z0-9\\-]+)/?$',
        APIResourceShow.as_view(), name='resource_show'
    ),
]
