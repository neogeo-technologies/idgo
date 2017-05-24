from django.conf.urls import url


from idgo_admin.views import *


urlpatterns = [
    url(r'^$', DatasetCreateV.as_view(), name='dataset'),
]