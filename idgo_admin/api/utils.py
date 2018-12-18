# Copyright (c) 2017-2018 Datasud.
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


from functools import wraps


def pagination_handler(f):
    _x = 1
    _y = 10

    def clean(value, default: int):
        try:
            value = int(value)
        except ValueError:
            return default
        else:
            return value > 0 and value or default

    @wraps(f)
    def wrapper(*args, **kwargs):
        x = clean(kwargs.pop('page_number', ''), _x)
        y = clean(kwargs.pop('page_size', ''), _y)
        i = (x * y) - y
        j = i + y
        kwargs.update({'i': i, 'j': j})
        return f(*args, **kwargs)
    return wrapper
