# Copyright (c) 2017-2021 Neogeo-Technologies.
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


# from django.apps import AppConfig


# class CeleriacConfig(AppConfig):
#     name = 'celeriac'
#     verbose_name = "Celeriac"


import os  # noqa
import importlib  # noqa

from celery import Celery  # noqa

from django.conf import settings  # noqa E402


try:
    CELERY_NAMESPACE = settings.CELERIAC_CELERY_NAMESPACE
except:
    CELERY_NAMESPACE = 'CELERY'


django_config_spec = importlib.util.find_spec('django_config')
if django_config_spec:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_config.settings')
else:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')


app = Celery('celeriac')
app.config_from_object('django.conf:settings', namespace=CELERY_NAMESPACE)
app.autodiscover_tasks()
