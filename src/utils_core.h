/*
 * Copyright 2017-2018 AVSystem <avsystem@avsystem.com>
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#ifndef ANJAY_UTILS_H
#define ANJAY_UTILS_H

#include <avsystem/commons/list.h>

#include <anjay_modules/raw_buffer.h>
#include <anjay_modules/utils_core.h>

#include <anjay/dm.h>

#include <stdbool.h>
#include <stddef.h>

VISIBILITY_PRIVATE_HEADER_BEGIN

#define anjay_log(...) _anjay_log(anjay, __VA_ARGS__)

int _anjay_safe_strtoll(const char *in, long long *value);
int _anjay_safe_strtod(const char *in, double *value);
int _anjay_safe_strtof(const char *in, float *value);

AVS_LIST(const anjay_string_t)
_anjay_copy_string_list(AVS_LIST(const anjay_string_t) input);

AVS_LIST(const anjay_string_t)
_anjay_make_string_list(const char *string,
                        ... /* strings */) AVS_F_SENTINEL;

// Const pointer cast is to ensure, that passed NULL will have the proper type,
// regardless of toolchain used
#define ANJAY_MAKE_STRING_LIST(...) \
    _anjay_make_string_list(__VA_ARGS__, (const char *) NULL)

AVS_LIST(const anjay_string_t)
_anjay_make_query_string_list(const char *version,
                              const char *endpoint_name,
                              const int64_t *lifetime,
                              anjay_binding_mode_t binding_mode,
                              const char *sms_msisdn);

#ifdef ANJAY_TEST
typedef uint32_t anjay_rand_seed_t;
#else
typedef unsigned anjay_rand_seed_t;
#endif
uint32_t _anjay_rand32(anjay_rand_seed_t *seed);

static inline void _anjay_update_ret(int *var, int new_retval) {
    if (!*var) {
        *var = new_retval;
    }
}

typedef struct {
    avs_net_af_t family;
    char (*last_local_port_buffer)[ANJAY_MAX_URL_PORT_SIZE];
    uint16_t static_port_preference;
} anjay_socket_bind_config_t;

int _anjay_bind_and_connect_socket(avs_net_abstract_socket_t *socket,
                                   const anjay_socket_bind_config_t *bind_conf,
                                   const char *remote_host,
                                   const char *remote_port);

int
_anjay_create_connected_udp_socket(avs_net_abstract_socket_t **out,
                                   avs_net_socket_type_t type,
                                   const void *socket_config,
                                   const anjay_socket_bind_config_t *bind_conf,
                                   const anjay_url_t *uri);

static inline size_t _anjay_max_power_of_2_not_greater_than(size_t bound) {
    int exponent = -1;
    while (bound) {
        bound >>= 1;
        ++exponent;
    }
    return (exponent >= 0) ? ((size_t) 1 << exponent) : 0;
}

VISIBILITY_PRIVATE_HEADER_END

#endif // ANJAY_UTILS_H
