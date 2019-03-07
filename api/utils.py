# Copyright (c) 2017-2019 Datasud.
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


from django.http.multipartparser import MultiPartParserError
from io import BytesIO


def parse_request(request):
    if hasattr(request, '_body'):
        data = BytesIO(request._body)
    else:
        data = request
    try:
        return request.parse_file_upload(request.META, data)
    except MultiPartParserError:
        request._mark_post_parse_error()
        raise
