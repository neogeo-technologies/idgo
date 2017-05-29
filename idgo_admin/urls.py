from django.conf.urls import url


from idgo_admin.views import *


urlpatterns = [
    url(r'^(?P<id>[0-9]+)/?$', DatasetUpdateV.as_view(), name='dataset_update'),
    url(r'^$', DatasetCreateV.as_view(), name='dataset'),
]