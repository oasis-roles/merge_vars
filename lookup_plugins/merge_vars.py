# Copyright 2019 Red Hat, Inc.
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.errors import AnsibleError
from ansible.module_utils.six import string_types
from ansible.plugins.lookup import LookupBase


class LookupModule(LookupBase):
    def run(self, terms, variables, **kwargs):
        try:
            term = terms[0]
            if not isinstance(term, string_types):
                raise ValueError
        except (IndexError, ValueError):
            raise AnsibleError('merge_var expects one string argument')

        ret = kwargs.get('initial', [])
        if kwargs.get('include_existing', False):
            existing = variables.get(term)
            if existing is not None:
                ret.append(existing)

        if not isinstance(ret, list):
            raise AnsibleError('merge_var initial value must be a list')

        # Makes use of the included merged_host_group_vars plugin to
        # prepopulate merged group and host var lists.
        for vartype in ('host_vars', 'group_vars'):
            if kwargs.get(vartype, True):
                merged_varname = '_merged_{}'.format(vartype)
                merged_var = variables.get(merged_varname, {})
                ret.extend(merged_var.get(term, []))
        return ret
