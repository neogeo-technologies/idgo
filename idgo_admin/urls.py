from django.conf.urls import url


from idgo_admin.views import *


urlpatterns = [

    url(r'^$', dataset, name='dataset'),
]