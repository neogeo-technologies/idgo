from django.conf.urls import url
from idgo_admin.views import DatasetManager


urlpatterns = [
    url('^$', DatasetManager.as_view(), name='dataset')]
