# Copyright (c) 2019 Neogeo-Technologies.
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


from rest_framework import routers

from sid.views.user import AgentViews
from sid.views.user import EmployeeViews
from sid.views.organisation import CompanyViews
from sid.views.organisation import OrganismViews


app_name = 'sid'

router = routers.DefaultRouter(trailing_slash=False)
router.register(r'agent', AgentViews, basename='agent')
router.register(r'employee', EmployeeViews, basename='employee')
router.register(r'organism', OrganismViews, basename='organism')
router.register(r'company', CompanyViews, basename='company')

urlpatterns = router.urls
