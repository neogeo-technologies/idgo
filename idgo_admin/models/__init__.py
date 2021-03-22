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


from idgo_admin.models.account import AccountActions
from idgo_admin.models.account import LiaisonsContributeurs
from idgo_admin.models.account import LiaisonsReferents
from idgo_admin.models.account import Profile
from idgo_admin.models.base_maps import BaseMaps
from idgo_admin.models.category import Category
from idgo_admin.models.data_type import DataType
from idgo_admin.models.dataset import Dataset
from idgo_admin.models.dataset import Keywords
from idgo_admin.models.extractor import AsyncExtractorTask
from idgo_admin.models.extractor import ExtractorSupportedFormat
from idgo_admin.models.gdpr import Gdpr
from idgo_admin.models.gdpr import GdprUser
from idgo_admin.models.granularity import Granularity
from idgo_admin.models.jurisdiction import Commune
from idgo_admin.models.jurisdiction import Jurisdiction
from idgo_admin.models.jurisdiction import JurisdictionCommune
from idgo_admin.models.layer import Layer
from idgo_admin.models.license import License
from idgo_admin.models.mail import Mail
from idgo_admin.models.organisation import Organisation
from idgo_admin.models.organisation import OrganisationType
from idgo_admin.models.resource import Resource
from idgo_admin.models.resource import ResourceFormats
from idgo_admin.models.support import Support
from idgo_admin.models.supported_crs import SupportedCrs
from idgo_admin.models.task import Task


__all__ = [
    AccountActions,
    AsyncExtractorTask,
    BaseMaps,
    Category,
    Commune,
    Dataset,
    DataType,
    ExtractorSupportedFormat,
    Granularity,
    Gdpr,
    GdprUser,
    Jurisdiction,
    JurisdictionCommune,
    Keywords,
    Layer,
    License,
    LiaisonsContributeurs,
    LiaisonsReferents,
    Mail,
    Organisation,
    OrganisationType,
    Profile,
    Resource,
    ResourceFormats,
    Support,
    SupportedCrs,
    Task,
]


from idgo_admin import ENABLE_CKAN_HARVESTER  # noqa
if ENABLE_CKAN_HARVESTER:

    from idgo_admin.models.organisation import RemoteCkan
    from idgo_admin.models.organisation import RemoteCkanDataset
    from idgo_admin.models.organisation import MappingCategory
    from idgo_admin.models.organisation import MappingLicence

    __all__ += [RemoteCkan, RemoteCkanDataset, MappingCategory, MappingLicence]


from idgo_admin import ENABLE_CSW_HARVESTER  # noqa
if ENABLE_CSW_HARVESTER:

    from idgo_admin.models.organisation import RemoteCsw
    from idgo_admin.models.organisation import RemoteCswDataset

    __all__ += [RemoteCsw, RemoteCswDataset]


from idgo_admin import ENABLE_DCAT_HARVESTER  # noqa
if ENABLE_DCAT_HARVESTER:

    from idgo_admin.models.organisation import RemoteDcat
    from idgo_admin.models.organisation import RemoteDcatDataset

    __all__ += [RemoteDcat, RemoteDcatDataset]
