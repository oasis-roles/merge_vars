[![Build Status](https://travis-ci.com/oasis-roles/merge_vars.svg?branch=master)](https://travis-ci.com/oasis-roles/merge_vars)

merge_vars
===========

A role containing custom plugins that allow you to merge `host_vars` and `group_vars`
across multiple hosts. This is most useful for `group_vars`, but `host_vars` are also
included in the merged output to allow for host-specific additions to the merged
`group_vars` result. This is different from Ansible's normal behavior, which is to
set a given variable to the most-recently-processed value as determined via variable
precedence.

This role is intended to help in situations when common variables are used in multiple
groups that apply to a single host. It was created to primary help in role-centric
playbooks that are configured with `group_vars`, in which hosts are "co-located",
and multiple roles (and therefore `group_vars`) apply to a single host.

See the Role Usage below for more detailed examples of where this might be useful.

Requirements
------------

Ansible 2.5 or higher

Role Usage
----------

This role is expected to be used where you want to merge the values of a variable defined
in multiple groups and pass that merged value into playbook tasks or variables used
in roles.

To use this function, include this role in your playbook, and use the `query` template
function to do a lookup using the `merge_vars` plugin:

`query('merge_vars', '<var_name_to_merge>')`

Optional keyword arguments include:

- `group_vars`: Default True, set to False to exclude group vars from the merged result
- `host_vars`: Default True, set to False to exclude host vars from the merged result
- `initial`: An optional list of values used to initialize the list of merged variable
  values returned by the query. This is useful in cases where you might want to include
  vars from sources other than host and group vars, or where you want to inject initial
  values for any reason. Value must be a list.

Practical Example
=================

A practical use of this role can be demonstrated with this scenario, which combines
lists of packages defined in several `group_vars` files.

 inventory looks like this:
```ini
[group_common]
host_one
host_two

[webserver]
host_one

[database]
host_two
```

Assume that the following `group_vars` files are in-use.

`group_vars/group_common`:
```yaml
install_packages:
  - common_package
  - duplicated_package
```

`group_vars/webserver`:
```yaml
install_packages:
  - webserver_package
  - duplicated_package
```

`group_vars/database`:
```yaml
install_packages:
  - database_package
  - duplicated_package
```

The following playbook can be used to install the expected packages on each host with
a single task:
```yaml
- hosts: all
  # The role must be referenced at least once in a playbook to use its included plugins.
  roles:
    - role: oasis_roles.merge_vars
  vars:
    merged_install_packages: "{{ query('merge_vars', 'install_packages') | flatten | unique }}"
  tasks:
    - name: install all packages based on host groups
      package:
        state: present
        name: "{{ merged_install_packages }}"
```

Filtering through `flatten` and `unique` ensures that the merged values are structured
in a way that's usable by the `package` module (assuming the underlying packaging module
is one of those that can accept a list for the `name` parameter).

The output of the `query`, for each host, would look like this:

```yaml
# host_one, note that the values from the "common" and "webserver" group vars are included
- [common_package, duplicated_package]
- [webserver_package, duplicated_package]

# host_two, note that the values from the "common" and "database" group vars are included
- [common_package, duplicated_package]
- [database_package, duplicated_package]
```

After running the result through the `flatten` filter, the results are transformed into this:

```yaml
# host_one
- common_package
- duplicated_package
- webserver_package
- duplicated_package

# host_two
- common_package
- duplicated_package
- database_package
- duplicated_package
```

And finally, filtering that with `unique` results in the final, flattened,
deduplicated list for use with the `package` module:

```yaml
# host_one
- common_package
- duplicated_package
- webserver_package

# host_two
- duplicated_package
- common_package
- database_package
```

Notes
=====


Lookup vs Query
---------------

Like all lookup plugins, this plugin can be invoked with either the
`lookup` or `query` template function. `query` will always return a list,
which makes it the more predictable choice for use with lookup plugins,
including this one.

See also:
https://docs.ansible.com/ansible/latest/user_guide/playbooks_loops.html#ensuring-list-input-for-loop-query-vs-lookup

Variable Definitions in Playbooks
---------------------------------

Lookup plugins, including this `merge_vars` plugins can be defined at the playbook
level, and will still be correctly templated per-host.

```yaml
- name: |-
    These play tasks will run with the same loop items based on the group_vars
    that apply to the current inventory host, based on its groups.
  hosts: all
  vars:
    playbook_var: "{{ query('merge_vars', 'your_var_name') }}"
  tasks:
    - name: use the playbook var in a loop
      debug:
        var: item
      loop: "{{ playbook_var }}"

    - name: merge vars dynamically for looping a task
      debug:
        var: item
      loop: "{{ query('merge_vars', 'your_var_name') }}"
```

Start with an initial value
---------------------------

In addition, existing playbook vars can be used with the `initial` keyword
argument to bring in vars from other sources, including existing vars.

```yaml
- name: |-
    Bring in existing vars via the "initial" keyword argument
  hosts: all
  vars:
    initial_var: example
    playbook_var: |
        {{ query('merge_vars', 'your_var_name',
           initial=['an arbitrary string', initial_var]) }}"
```

`loop` and `with_merge_vars`
----------------------------

Variable merging is done with a lookup plugin to Ansible, which means that tasks
can use `with_merge_vars`, similar to `with_items`, or any other `with_<lookup>`
mechanism.

However, as recommended in
[the ansible documentation](https://docs.ansible.com/ansible/latest/user_guide/playbooks_loops.html#migrating-from-with-x-to-loop)
about loops, using the `loop` keyword is preferred, as it allows you to chain
lookups and queries with filters. In the package installation example above,
if you are using one of the package modules that does not accept a list for
the `name` parameter, you could instead `loop` over the results of a query:

```yaml
  tasks:
    - name: install all packages based on host groups
      package:
        state: present
      loop: "{{ query('merge_vars', 'install_packages') | flatten | unique }}"
```

Technical Details
=================

This role introduces two plugins to ansible. The first, a vars plugin, is very similar to the
built-in `host_group_vars` plugin, which inserts the values for host and group vars into the
runtime environment of ansible for a given host. The new plugin, `merged_host_group_vars`,
differs from the built-in plugin in that it aggregates all values seen in host and group vars,
rather than replacing the value for a given var with each new instance of that var seen in
host and group vars. This plugin stashes the merged values in "private" vars,
`_merged_host_vars` and `_merged_group_vars`. Two vars are used here so that they can be
easily discovered, and also so that it's easy to separate host vars from group vars.

The second plugin, a lookup plugin, picks up at this point. It is able to inspect the variable
set that ansible has determined for the current host, including the `_merged_*_vars` variables
set by the `merged_host_group_vars` plugin. Using those vars, and based on the options passed
in to the `merge_vars` query, the lookup plugin is then able to return a list of values for
a given variable seen in host and group vars.

Two separate plugins are needed for the following reasons:
- vars plugins are the correct way to read `host_vars` and `group_vars` files and insert the
  values found in them into a host's variable namespace. vars plugins are not able to
  read the current host's variable values, they are only able to insert values.
- lookup plugins are able to read all of the variables for a host, but cannot insert new
  values. lookup plugins also cannot determine if those variables were defined in
  `host_vars` or `group_vars` for the purposes of merging those values.

Those two reasons combined result in the `_merged_*_vars` used to pass the merged host
and group vars through the lookup plugin to the user.

Finally, care was taken to allow for any valid ansible data structure to be merged into
a list, with the specific intention being that the user would use ansible filters as
needed to restructure the queried data for use in tasks.

Dependencies
============

None

License
=======

GPLv3

Author Information
==================

Sean Myers <sean.myers@redhat.com>
