from django.conf.urls import url


from idgo_admin.views import *


urlpatterns = [
    url(r'^$', DatasetCreateV.as_view(), name='dataset'),
    url(r'^mydatasets/?$', DatasetDisplayV.as_view(), name='dataset_display'),
]