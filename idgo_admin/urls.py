from django.conf.urls import url
from idgo_admin.views import DatasetManager
from idgo_admin.views import ResourceManager


urlpatterns = [
    url('^$', DatasetManager.as_view(), name='dataset'),
    url('^(?P<dataset_id>(\d+))/resources/?$', ResourceManager.as_view(),
        name='resource'),
    ]
