#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2017-2018 AVSystem <avsystem@avsystem.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import argparse
import collections
import textwrap
import operator
import sys
import re
from xml.etree import ElementTree
from xml.etree.ElementTree import Element
from typing import Mapping, Tuple, Optional
from jinja2 import Environment

C_OBJDEF_TEMPLATE = """\
static const anjay_dm_object_def_t OBJ_DEF = {
    .oid = {{ oid }},
    .supported_rids = ANJAY_DM_SUPPORTED_RIDS(
{% for res in resources %}
                {{ res.name_upper }}{{ "" if loop.last else "," }}
{% endfor %}
            ),
    .handlers = {
{% for handler in handlers %}
{% if handler is string %}
{{ '' if handler == '' else '        ' + handler }}
{% else %}
        {{ '.%s = %s' % handler }}{{ "" if loop.last else "," }}
{% endif %}
{% endfor %}
    }
};
"""

CXX_OBJDEF_TEMPLATE = """\
namespace {

const uint16_t OBJ_SUPPORTED_RIDS[] = {
{% for res in resources %}
    {{ res.name_upper }}{{ "" if loop.last else "," }}
{% endfor %}
};

struct ObjDef : public anjay_dm_object_def_t {
    ObjDef() :
            anjay_dm_object_def_t() {
        oid = {{ oid }};
        supported_rids.count = AVS_ARRAY_SIZE(OBJ_SUPPORTED_RIDS);
        supported_rids.rids = OBJ_SUPPORTED_RIDS;

{% for handler in handlers %}
{% if handler is string %}
{{ '' if handler == '' else '        ' + handler }}
{% else %}
        {{ 'handlers.%s = %s;' % handler }}
{% endif %}
{% endfor %}
    }
} const OBJ_DEF;

}
"""

TEMPLATE = """\
/**
 * Generated by anjay_codegen.py on {{ date_time }}
 *
 * LwM2M Object: {{ obj.name }}
 * ID: {{ obj.oid }}, URN: {{ obj.urn }}, {{ obj.mandatory_str }}, {{ obj.multiple_str }}
 *
 * {{ obj.description }}
 */
#include <assert.h>
#include <stdbool.h>

#include <anjay/anjay.h>
#include <avsystem/commons/defs.h>
#include <avsystem/commons/memory.h>
{% if obj.multiple %}
#include <avsystem/commons/list.h>
{% endif %}

{% for res in obj.resources %}
/**
 * {{ res.name }}: {{ res.operations }}, {{ res.multiple_str }}, {{ res.mandatory_str }}
 * type: {{ res.type }}, range: {{ res.range_enumeration }}, unit: {{ res.units }}
 * {{ res.description }}
 */
#define {{ res.name_upper }} {{ res.rid }}

{% endfor %}
{% if obj.multiple %}
typedef struct {{ obj_inst_tag }} {
    anjay_iid_t iid;

    // TODO: instance state
} {{ obj_inst_type }};

{% endif %}
typedef struct {{ obj_repr_tag }} {
    const anjay_dm_object_def_t *def;
{% if obj.multiple %}
    AVS_LIST({{ obj_name_snake }}_instance_t) instances;
{% endif %}

    // TODO: object state
} {{ obj_repr_type }};

static inline {{ obj_repr_type }} *
get_obj(const anjay_dm_object_def_t *const *obj_ptr) {
    assert(obj_ptr);
    return AVS_CONTAINER_OF(obj_ptr, {{ obj_repr_type }}, def);
}

{% if obj.multiple %}
static {{ obj_inst_type }} *
find_instance(const {{ obj_repr_type }} *obj,
              anjay_iid_t iid) {
    AVS_LIST({{ obj_inst_type }}) it;
    AVS_LIST_FOREACH(it, obj->instances) {
        if (it->iid == iid) {
            return it;
        } else if (it->iid > iid) {
            break;
        }
    }

    return NULL;
}

static int instance_present(anjay_t *anjay,
                            const anjay_dm_object_def_t *const *obj_ptr,
                            anjay_iid_t iid) {
    (void)anjay;
    return find_instance(get_obj(obj_ptr), iid) != NULL;
}

static int instance_it(anjay_t *anjay,
                       const anjay_dm_object_def_t *const *obj_ptr,
                       anjay_iid_t *out,
                       void **cookie) {
    (void)anjay;

    AVS_LIST({{ obj_inst_type }}) curr = (AVS_LIST({{ obj_inst_type }}))*cookie;
    if (!curr) {
        curr = get_obj(obj_ptr)->instances;
    } else {
        curr = AVS_LIST_NEXT(curr);
    }

    *out = curr ? curr->iid : ANJAY_IID_INVALID;
    *cookie = curr;
    return 0;
}

static anjay_iid_t get_new_iid(AVS_LIST({{ obj_inst_type }}) instances) {
    anjay_iid_t iid = 1;
    AVS_LIST({{ obj_inst_type }}) it;
    AVS_LIST_FOREACH(it, instances) {
        if (it->iid == iid) {
            ++iid;
        } else if (it->iid > iid) {
            break;
        }
    }
    return iid;
}

static int init_instance({{ obj_inst_type }} *inst,
                         anjay_iid_t iid) {
    assert(iid != ANJAY_IID_INVALID);

    inst->iid = iid;
    // TODO: instance init

    // TODO: return 0 on success, negative value on failure
    return 0;
}

static void release_instance({{ obj_inst_type }} *inst) {
    // TODO: instance cleanup
    (void) inst;
}

static int instance_create(anjay_t *anjay,
                           const anjay_dm_object_def_t *const *obj_ptr,
                           anjay_iid_t *inout_iid,
                           anjay_ssid_t ssid) {
    (void) anjay; (void) ssid;
    {{ obj_repr_type }} *obj = get_obj(obj_ptr);
    assert(obj);

    AVS_LIST({{ obj_inst_type }}) created = AVS_LIST_NEW_ELEMENT({{ obj_inst_type }});
    if (!created) {
        return ANJAY_ERR_INTERNAL;
    }

    if (*inout_iid == ANJAY_IID_INVALID) {
        *inout_iid = get_new_iid(obj->instances);
    }

    int result = ANJAY_ERR_INTERNAL;
    if (*inout_iid == ANJAY_IID_INVALID
            || (result == init_instance(created, *inout_iid))) {
        AVS_LIST_CLEAR(&created);
        return result;
    }

    AVS_LIST({{ obj_inst_type }}) *ptr;
    AVS_LIST_FOREACH_PTR(ptr, &obj->instances) {
        if ((*ptr)->iid > created->iid) {
            break;
        }
    }

    AVS_LIST_INSERT(ptr, created);
    return 0;
}

static int instance_remove(anjay_t *anjay,
                           const anjay_dm_object_def_t *const *obj_ptr,
                           anjay_iid_t iid) {
    (void)anjay;
    {{ obj_repr_type }} *obj = get_obj(obj_ptr);
    assert(obj);

    AVS_LIST({{ obj_inst_type }}) *it;
    AVS_LIST_FOREACH_PTR(it, &obj->instances) {
        if ((*it)->iid == iid) {
            release_instance(*it);
            AVS_LIST_DELETE(it);
            return 0;
        } else if ((*it)->iid > iid) {
            break;
        }
    }

    assert(0);
    return ANJAY_ERR_NOT_FOUND;
}

{% endif %}
{% if obj.needs_instance_reset_handler %}
static int instance_reset(anjay_t *anjay,
                          const anjay_dm_object_def_t *const *obj_ptr,
                          anjay_iid_t iid) {
    (void) anjay;

    {{ obj_repr_type }} *obj = get_obj(obj_ptr);
    assert(obj);
{% if obj.multiple %}
    {{ obj_inst_type }} *inst = find_instance(obj, iid);
    assert(inst);
{% else %}
    assert(iid == 0);
{% endif %}

    // TODO: instance reset
    return 0;
}

{% endif %}
{% if obj.has_any_readable_resources %}
static int resource_read(anjay_t *anjay,
                         const anjay_dm_object_def_t *const *obj_ptr,
                         anjay_iid_t iid,
                         anjay_rid_t rid,
                         anjay_output_ctx_t *ctx) {
    (void)anjay;

    {{ obj_repr_type }} *obj = get_obj(obj_ptr);
    assert(obj);
{% if obj.multiple %}
    {{ obj_inst_type }} *inst = find_instance(obj, iid);
    assert(inst);
{% else %}
    assert(iid == 0);
{% endif %}

    switch (rid) {
{% for res in obj.resources %}
{% if 'R' in res.operations %}
    case {{ res.name_upper }}:
        {{ res.read_handler|indent(8) }}

{% endif %}
{% endfor %}
    default:
        return ANJAY_ERR_METHOD_NOT_ALLOWED;
    }
}

{% endif %}
{% if obj.has_any_writable_resources %}
static int resource_write(anjay_t *anjay,
                          const anjay_dm_object_def_t *const *obj_ptr,
                          anjay_iid_t iid,
                          anjay_rid_t rid,
                          anjay_input_ctx_t *ctx) {
    (void)anjay;

    {{ obj_repr_type }} *obj = get_obj(obj_ptr);
    assert(obj);
{% if obj.multiple %}
    {{ obj_inst_type }} *inst = find_instance(obj, iid);
    assert(inst);
{% else %}
    assert(iid == 0);
{% endif %}

    switch (rid) {
{% for res in obj.resources %}
{% if 'W' in res.operations %}
    case {{ res.name_upper }}:
        {{ res.write_handler|indent(8) }}

{% endif %}
{% endfor %}
    default:
        return ANJAY_ERR_METHOD_NOT_ALLOWED;
    }
}

{% endif %}
{% if obj.has_any_executable_resources %}
static int resource_execute(anjay_t *anjay,
                            const anjay_dm_object_def_t *const *obj_ptr,
                            anjay_iid_t iid,
                            anjay_rid_t rid,
                            anjay_execute_ctx_t *arg_ctx) {
    (void)arg_ctx;

    {{ obj_repr_type }} *obj = get_obj(obj_ptr);
    assert(obj);
{% if obj.multiple %}
    {{ obj_inst_type }} *inst = find_instance(obj, iid);
    assert(inst);
{% else %}
    assert(iid == 0);
{% endif %}

    switch (rid) {
{% for res in obj.resources %}
{% if 'E' in res.operations %}
    case {{ res.name_upper }}:
        return ANJAY_ERR_NOT_IMPLEMENTED; // TODO

{% endif %}
{% endfor %}
    default:
        return ANJAY_ERR_METHOD_NOT_ALLOWED;
    }
}

{% endif %}
{% if obj.has_any_multiple_resources %}
static int resource_dim(anjay_t *anjay,
                        const anjay_dm_object_def_t *const *obj_ptr,
                        anjay_iid_t iid,
                        anjay_rid_t rid) {
    (void) anjay;

    {{ obj_repr_type }} *obj = get_obj(obj_ptr);
    assert(obj);
{% if obj.multiple %}
    {{ obj_inst_type }} *inst = find_instance(obj, iid);
    assert(inst);
{% else %}
    assert(iid == 0);
{% endif %}

    switch (rid) {
{% for res in obj.resources %}
{% if res.multiple %}
    case {{ res.name_upper }}:
        return 1; // TODO

{% endif %}
{% endfor %}
    default:
        return ANJAY_DM_DIM_INVALID;
    }
}

{% endif %}
{{ cdef }}

const anjay_dm_object_def_t **{{ obj_name_snake }}_object_create(void) {
    {{ obj_repr_type }} *obj = ({{ obj_repr_type }} *)
            avs_calloc(1, sizeof({{ obj_repr_type }}));
    if (!obj) {
        return NULL;
    }
    obj->def = &OBJ_DEF;

    // TODO: object init

    return &obj->def;
}

void {{ obj_name_snake }}_object_release(const anjay_dm_object_def_t **def) {
    if (def) {
        {{ obj_repr_type }} *obj = get_obj(def);
{% if obj.multiple %}
        AVS_LIST_CLEAR(&obj->instances) {
            release_instance(obj->instances);
        }
{% endif %}

        // TODO: object cleanup

        avs_free(obj);
    }
}
"""


def _node_text(n: Element) -> str:
    return (n.text if n.text is not None else '').strip()


def _sanitize_macro_name(n: str) -> str:
    return re.sub(r'[^a-zA-Z0-9]+', '_', n).strip('_')


class ResourceDef(collections.namedtuple('ResourceDef', ['rid', 'name', 'operations', 'multiple', 'mandatory', 'type',
                                                         'range_enumeration', 'units', 'description'])):
    @property
    def mandatory_str(self) -> str:
        return 'Mandatory' if self.mandatory else 'Optional'

    @property
    def multiple_str(self):
        return 'Multiple' if self.multiple else 'Single'

    @property
    def name_upper(self) -> str:
        return _sanitize_macro_name('RID_' + self.name.upper())

    @property
    def read_handler(self) -> Optional[str]:
        if 'R' not in self.operations:
            return None

        types = [
            (('boolean', 'bool'), 'anjay_ret_bool(%s, 0)'),
            (('integer', 'int'), 'anjay_ret_i32(%s, 0)'),
            (('float',), 'anjay_ret_float(%s, 0)'),
            (('string', 'str'), 'anjay_ret_string(%s, "")'),
            (('opaque',), 'anjay_ret_bytes(%s, "", 0)'),
            (('time',), 'anjay_ret_i64(%s, 0)'),
            (('objlnk',), 'anjay_ret_objlnk(%s, 0, 0)'),
        ]

        def get_ret_func(type):
            for match_types, ret_func in types:
                if type in match_types:
                    return ret_func
            else:
                raise AssertionError('unexpected type: ' + type)

        if not self.multiple:
            return 'return %s; // TODO' % (get_ret_func(self.type) % ('ctx',))
        else:
            return textwrap.dedent("""\
                    {
                        anjay_output_ctx_t *array = anjay_ret_array_start(ctx);
                        int result = 0;
                        if (!array
                                || (result = anjay_ret_array_index(array, 0))
                                || (result = %s)) {
                            return result ? result : ANJAY_ERR_INTERNAL;
                        }
                        return anjay_ret_array_finish(array);
                    }
                    """) % (get_ret_func(self.type) % ('array',))


    @property
    def write_handler(self) -> Optional[Tuple[str, str]]:
        if 'W' not in self.operations:
            return None

        types = [
            (('boolean', 'bool'), 'bool value',      'anjay_get_bool(%s, &value)'),
            (('integer', 'int'),  'int32_t value',   'anjay_get_i32(%s, &value)'),
            (('float',),          'float value',     'anjay_get_float(%s, &value)'),
            (('string', 'str'),   'char value[256]', 'anjay_get_string(%s, value, sizeof(value))'),
            (('opaque',),
                 'uint8_t value[256];\n'
                 '    bool finished;\n'
                 '    size_t bytes_read',
                 'anjay_get_bytes(%s, &bytes_read, &finished, value, sizeof(value))'),
            (('time',),           'int64_t value',   'anjay_get_i64(%s, &value)'),
            (('objlnk',),
                'anjay_oid_t oid;\n'
                '    anjay_iid_t iid',
                'anjay_get_objlnk(%s, &oid, &iid)'),
        ]


        def get_get_func(type):
            for match_types, alloc_value, get_func in types:
                if type in match_types:
                    return alloc_value, get_func
            else:
                raise AssertionError('unexpected type: ' + type)

        local_def, get_func = get_get_func(self.type.lower())
        if not self.multiple:
            get_func %= ('ctx',)
            return textwrap.dedent("""\
                    {
                        %s; // TODO
                        return %s; // TODO
                    }
                    """) % (local_def, get_func)
        else:
            get_func %= ('array',)
            return textwrap.dedent("""\
                    {
                        anjay_input_ctx_t *array = anjay_get_array(ctx);
                        if (!array) {
                            return ANJAY_ERR_INTERNAL;
                        }

                        anjay_riid_t riid;
                        int result = 0;
                        %s; // TODO
                        while (result == 0 && (result = anjay_get_array_index(array, &riid)) == 0) {
                            result = %s; // TODO
                        }

                        return result;
                    }
                    """) % (local_def, get_func)

    @classmethod
    def from_etree(cls, res: Element) -> 'ResourceDef':
        return cls(rid=int(res.get('ID')),
                   name=_node_text(res.find('Name')),
                   operations=_node_text(res.find('Operations')).upper(),
                   multiple={'Single': False, 'Multiple': True}[_node_text(res.find('MultipleInstances'))],
                   mandatory={'Optional': False, 'Mandatory': True}[_node_text(res.find('Mandatory'))],
                   type=(_node_text(res.find('Type')).lower() or 'N/A'),
                   range_enumeration=(_node_text(res.find('RangeEnumeration')) or 'N/A'),
                   units=(_node_text(res.find('Units')) or 'N/A'),
                   description=textwrap.fill(_node_text(res.find('Description'))).replace('\n', '\n * '))


class ObjectDef(collections.namedtuple('ObjectDef',
                                       ['oid', 'name', 'description', 'urn', 'multiple', 'mandatory', 'resources'])):
    @property
    def name_snake(self) -> str:
        return self.name.lower().replace(' ', '_')

    @property
    def mandatory_str(self) -> str:
        return 'Mandatory' if self.mandatory else 'Optional'

    @property
    def multiple_str(self):
        return 'Multiple' if self.multiple else 'Single'

    @property
    def has_any_readable_resources(self) -> bool:
        return any('R' in res.operations for res in self.resources)

    @property
    def has_any_writable_resources(self) -> bool:
        return any('W' in res.operations for res in self.resources)

    @property
    def has_any_executable_resources(self) -> bool:
        return any('E' in res.operations for res in self.resources)

    @property
    def has_any_multiple_resources(self) -> bool:
        return any(res.multiple for res in self.resources)

    @property
    def needs_instance_reset_handler(self) -> bool:
        return self.multiple or self.has_any_writable_resources

    @classmethod
    def from_etree(cls, obj: ElementTree) -> 'ObjectDef':
        return cls(name=_node_text(obj.find('Name')),
                   description=textwrap.fill(_node_text(obj.find('Description1'))).replace('\n', '\n * '),
                   oid=int(_node_text(obj.find('ObjectID'))),
                   urn=_node_text(obj.find('ObjectURN')),
                   multiple={'Single': False, 'Multiple': True}[_node_text(obj.find('MultipleInstances'))],
                   mandatory={'Optional': False, 'Mandatory': True}[_node_text(obj.find('Mandatory'))],
                   resources=sorted([ResourceDef.from_etree(item) for item in obj.find('Resources').findall('Item')],
                                    key=operator.attrgetter('rid')))


def generate_object_boilerplate(obj_ddf_xml: str, cxx: bool):
    tree = ElementTree.fromstring(obj_ddf_xml)
    obj = ObjectDef.from_etree(tree.find('Object'))

    jinja_env = Environment(trim_blocks=True)

    handlers = []
    if obj.multiple:
        handlers.append(('instance_it', 'instance_it'))
        handlers.append(('instance_present', 'instance_present'))
        handlers.append(('instance_create', 'instance_create'))
        handlers.append(('instance_remove', 'instance_remove'))
    else:
        handlers.append(('instance_it', 'anjay_dm_instance_it_SINGLE'))
        handlers.append(('instance_present', 'anjay_dm_instance_present_SINGLE'))

    if obj.needs_instance_reset_handler:
        handlers.append(('instance_reset', 'instance_reset'))

    handlers.append('')
    handlers.append(('resource_present', 'anjay_dm_resource_present_TRUE'))
    if obj.has_any_readable_resources:
        handlers.append(('resource_read', 'resource_read'))
    if obj.has_any_writable_resources:
        handlers.append(('resource_write', 'resource_write'))
    if obj.has_any_executable_resources:
        handlers.append(('resource_execute', 'resource_execute'))
    if obj.has_any_multiple_resources:
        handlers.append(('resource_dim', 'resource_dim'))

    handlers.append('')
    handlers.append('// TODO: implement these if transactional write/create is required')
    handlers.append(('transaction_begin', 'anjay_dm_transaction_NOOP'))
    handlers.append(('transaction_validate', 'anjay_dm_transaction_NOOP'))
    handlers.append(('transaction_commit', 'anjay_dm_transaction_NOOP'))
    handlers.append(('transaction_rollback', 'anjay_dm_transaction_NOOP'))

    cdef = (jinja_env
                .from_string(CXX_OBJDEF_TEMPLATE if cxx else C_OBJDEF_TEMPLATE)
                .render(oid=obj.oid, resources=obj.resources, handlers=handlers))

    return (jinja_env.from_string(TEMPLATE)
                .render(obj=obj,
                        date_time=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        obj_name_snake=obj.name_snake,
                        obj_repr_tag=obj.name_snake + '_struct',
                        obj_repr_type=obj.name_snake + '_t',
                        obj_inst_tag=obj.name_snake + '_instance_struct',
                        obj_inst_type=obj.name_snake + '_instance_t',
                        cdef=cdef))


if __name__ == '__main__':
    parser = argparse.ArgumentParser('Parses an LwM2M object definition XML and generates Anjay object skeleton')
    parser.add_argument('-i', '--input', help='Input filename or - to read from stdin')
    parser.add_argument('-o', '--output', default='/dev/stdout', help='Output filename (default: stdout)')
    parser.add_argument('-x', '--c++', dest='cxx', action='store_true', help='Generate C++ code (default: C)')

    args = parser.parse_args()
    if args.input == '-':
        args.input = '/dev/stdin'
    if args.output == '-':
        args.output = '/dev/stdout'

    if args.input is None:
        parser.print_usage()
        sys.exit(1)

    with open(args.input) as f:
        boilerplate = generate_object_boilerplate(f.read(), args.cxx)

    with open(args.output, 'w') as f:
        print(boilerplate, file=f)
