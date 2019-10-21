# Copyright 2017, 2019 Red Hat, Inc.
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
#
# This program is a derivative work based on the Ansible built-in
# "host_group_vars" vars plugin, which at the time of derivation
# was copyrighted and licensed under the same terms as this program.
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import os
from collections import defaultdict

from ansible.module_utils._text import to_bytes, to_text
from ansible.plugins.vars import BaseVarsPlugin
from ansible.inventory.host import Host
from ansible.inventory.group import Group

FOUND = {}


class VarsModule(BaseVarsPlugin):
    def get_vars(self, loader, path, entities, cache=True):
        ''' parses the inventory file '''

        if not isinstance(entities, list):
            entities = [entities]

        super(VarsModule, self).get_vars(loader, path, entities)

        data = {}

        # host and group vars are handled in separate calls to
        # this plugin. While they could be potentially merged,
        # they are kept separate here to make it easier to allow
        # the user to optionally filter out host or group vars later
        _merged_vars = defaultdict(lambda: defaultdict(list))

        for entity in entities:
            if isinstance(entity, Host):
                subdir = 'host_vars'
            elif isinstance(entity, Group):
                subdir = 'group_vars'
            else:
                # Builtin host_group_vars throws an error here,
                # but this plugin can ignore unknown entity types
                # and let the builtin plugin handle error cases so
                # there's only one plugin complaining about this
                continue

            # avoid 'chroot' type inventory hostnames /path/to/chroot
            if entity.name.startswith(os.path.sep):
                continue

            try:
                found_files = []
                # load vars
                b_opath = os.path.realpath(to_bytes(os.path.join(self._basedir, subdir)))
                opath = to_text(b_opath)
                key = '%s.%s' % (entity.name, opath)
                if cache and key in FOUND:
                    found_files = FOUND[key]
                else:
                    # no need to do much if path does not exist for basedir
                    if os.path.exists(b_opath):
                        if os.path.isdir(b_opath):
                            self._display.debug("\tprocessing dir %s" % opath)
                            found_files = loader.find_vars_files(opath, entity.name)
                            FOUND[key] = found_files

                for found in found_files:
                    new_data = loader.load_from_file(found, cache=True, unsafe=True)
                    # This is the major change from the builtin host_group_vars
                    # plugin, which doesn't provide entry points for easily
                    # overriding its behavior. Here, instead of merging the
                    # resolved vars into a dict, values are aggregated into a
                    # list for merging later by the included lookup plugin.
                    if new_data:
                        for k, v in new_data.items():
                            _merged_vars[subdir][k].append(v)

            except Exception:
                # Again, the builtin plugin throws an error in this case,
                # but this plugin ignores those errors and allows the
                # builtin plugin to handle them.
                continue

            # Only add merged data to the return value if data was merged
            if _merged_vars[subdir]:
                # "data_key" is the actual variable name created by this
                # plugin, which is then used by the lookup plugin counterpart
                # to expose these merged vars to the user
                data_key = '_merged_%s' % (subdir)
                data[data_key] = _merged_vars[subdir]
        return data
