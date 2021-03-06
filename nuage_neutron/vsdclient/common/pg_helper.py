# Copyright 2016 NOKIA
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import logging
import netaddr

from nuage_neutron.vsdclient.common.cms_id_helper import get_vsd_external_id
from nuage_neutron.vsdclient.common import constants
from nuage_neutron.vsdclient.common import helper
from nuage_neutron.vsdclient.common import nuagelib
from nuage_neutron.vsdclient import restproxy

VSD_RESP_OBJ = constants.VSD_RESP_OBJ

LOG = logging.getLogger(__name__)


def get_l3dom_policygroup_by_sgid(restproxy_serv, l3dom_id, sg_id):
    req_params = {
        'domain_id': l3dom_id,
        'externalID': get_vsd_external_id(sg_id)
    }

    nuage_policygroup = nuagelib.NuagePolicygroup(create_params=req_params)
    response = restproxy_serv.rest_call(
        'GET', nuage_policygroup.post_resource(), '',
        extra_headers=nuage_policygroup.extra_headers_get())

    if not nuage_policygroup.validate(response):
        raise restproxy.RESTProxyError(nuage_policygroup.error_msg)

    if not response[3]:
        return response[3]
    else:
        return nuage_policygroup.get_policygroup_id(response)


def get_l2dom_policygroup_by_sgid(restproxy_serv, l2dom_id, sg_id):
    req_params = {
        'domain_id': l2dom_id,
        'externalID': get_vsd_external_id(sg_id)
    }

    nuage_policygroup = nuagelib.NuagePolicygroup(create_params=req_params)
    response = restproxy_serv.rest_call(
        'GET', nuage_policygroup.post_resource_l2dom(), '',
        extra_headers=nuage_policygroup.extra_headers_get())

    if not nuage_policygroup.validate(response):
        raise restproxy.RESTProxyError(nuage_policygroup.error_msg)

    if not response[3]:
        nuage_policygroup_id = response[3]
    else:
        nuage_policygroup_id = nuage_policygroup.get_policygroup_id(response)
    return nuage_policygroup_id


def get_policygroup_by_sgid(restproxy_serv, params):
    neutron_rtr_id = params.get('neutron_rtr_id', None)
    l3dom_id = None
    l2dom_id = params.get('l2dom_id')
    if neutron_rtr_id:
        l3dom_id = helper.get_l3domid_by_router_id(restproxy_serv,
                                                   neutron_rtr_id)
        policygroup_id = get_l3dom_policygroup_by_sgid(
            restproxy_serv, l3dom_id, params['sg_id'])
    else:
        policygroup_id = get_l2dom_policygroup_by_sgid(
            restproxy_serv, params.get('l2dom_id'), params['sg_id'])

    result = {
        'nuage_rtr_id': l3dom_id,
        'nuage_l2dom_id': l2dom_id,
        'policygroup_id': policygroup_id
    }

    return result


def get_l3dom_inbound_acl_id(restproxy_serv, dom_id):
    req_params = {
        'parent_id': dom_id
    }
    nuageibacl = nuagelib.NuageInboundACL(create_params=req_params)
    default_l3_acl_name = dom_id + constants.NUAGE_DEFAULT_L3_INGRESS_ACL
    extra_headers = nuageibacl.extra_headers_get_by_name(default_l3_acl_name)
    response = restproxy_serv.rest_call('GET',
                                        nuageibacl.get_resource_l3(), '',
                                        extra_headers=extra_headers)
    if not nuageibacl.get_validate(response):
        raise restproxy.RESTProxyError(nuageibacl.error_msg)
    nuageibacl_id = nuageibacl.get_iacl_id(response)

    return nuageibacl_id


def get_l3dom_outbound_acl_id(restproxy_serv, dom_id):
    req_params = {
        'parent_id': dom_id
    }
    nuageobacl = nuagelib.NuageOutboundACL(create_params=req_params)
    default_l3_acl_name = dom_id + constants.NUAGE_DEFAULT_L3_EGRESS_ACL
    extra_headers = nuageobacl.extra_headers_get_by_name(default_l3_acl_name)
    response = restproxy_serv.rest_call('GET',
                                        nuageobacl.get_resource_l3(), '',
                                        extra_headers=extra_headers)
    if not nuageobacl.get_validate(response):
        raise restproxy.RESTProxyError(nuageobacl.error_msg)
    nuageobacl_id = nuageobacl.get_oacl_id(response)

    return nuageobacl_id


def get_l2dom_inbound_acl_id(restproxy_serv, dom_id):
    req_params = {
        'parent_id': dom_id
    }
    nuageibacl = nuagelib.NuageInboundACL(create_params=req_params)
    default_l2_acl_name = dom_id + constants.NUAGE_DEFAULT_L2_INGRESS_ACL
    extra_headers = nuageibacl.extra_headers_get_by_name(default_l2_acl_name)
    response = restproxy_serv.rest_call('GET',
                                        nuageibacl.get_resource_l2(), '',
                                        extra_headers=extra_headers)
    if not nuageibacl.get_validate(response):
        raise restproxy.RESTProxyError(nuageibacl.error_msg)
    nuageibacl_id = nuageibacl.get_iacl_id(response)

    return nuageibacl_id


def get_l2dom_outbound_acl_id(restproxy_serv, dom_id):
    req_params = {
        'parent_id': dom_id
    }
    nuageobacl = nuagelib.NuageOutboundACL(create_params=req_params)
    default_l2_acl_name = dom_id + constants.NUAGE_DEFAULT_L2_EGRESS_ACL
    extra_headers = nuageobacl.extra_headers_get_by_name(default_l2_acl_name)
    response = restproxy_serv.rest_call('GET',
                                        nuageobacl.get_resource_l2(), '',
                                        extra_headers=extra_headers)
    if not nuageobacl.get_validate(response):
        raise restproxy.RESTProxyError(nuageobacl.error_msg)
    nuageobacl_id = nuageobacl.get_oacl_id(response)

    return nuageobacl_id


def get_inbound_acl_details(restproxy_serv, dom_id, type=constants.SUBNET):
    req_params = {
        'parent_id': dom_id
    }
    nuageibacl = nuagelib.NuageInboundACL(create_params=req_params)
    if type == constants.L2DOMAIN:
        default_acl_name = dom_id + constants.NUAGE_DEFAULT_L2_INGRESS_ACL
        url = nuageibacl.get_resource_l2()
    else:
        default_acl_name = dom_id + constants.NUAGE_DEFAULT_L3_INGRESS_ACL
        url = nuageibacl.get_resource_l3()
    extra_headers = nuageibacl.extra_headers_get_by_name(default_acl_name)
    response = restproxy_serv.rest_call('GET',
                                        url, '',
                                        extra_headers=extra_headers)
    if not nuageibacl.get_validate(response):
        raise restproxy.RESTProxyError(nuageibacl.error_msg)
    return response[3][0]


def _get_remote_policygroup_id(restproxy_serv, sg_id, resourcetype,
                               resource_id, sg_name):
    req_params = {
        'name': sg_name,
        'domain_id': resource_id,
        'sg_id': sg_id,
        'externalID': get_vsd_external_id(sg_id)
    }

    nuage_policygroup = nuagelib.NuagePolicygroup(create_params=req_params)
    if resourcetype == 'l3domain':
        url = nuage_policygroup.post_resource()
    else:
        url = nuage_policygroup.post_resource_l2dom()
    policygroups = restproxy_serv.get(
        url, extra_headers=nuage_policygroup.extra_headers_get(),
        required=True)
    if policygroups:
        return policygroups[0]['ID']
    else:
        policygroups = restproxy_serv.post(
            url,
            nuage_policygroup.post_data())
        return policygroups[0]['ID']


def _create_nuage_prefix_macro(restproxy_serv, sg_rule, np_id):
    net = netaddr.IPNetwork(sg_rule['remote_ip_prefix'])
    macro_name = (np_id + '_' + str(int(net.ip)) + '_' +
                  str(int(net.netmask)))
    req_params = {
        'net_partition_id': np_id,
        'net': net,
        'name': macro_name
    }
    nuage_np_net = nuagelib.NuageNetPartitionNetwork(
        create_params=req_params)
    response = restproxy_serv.rest_call(
        'GET',
        nuage_np_net.get_resource(), '',
        nuage_np_net.extra_headers_get_netadress(
            str(net.ip), str(net.netmask)))
    pubnet_id = None
    if not nuage_np_net.validate(response):
        raise restproxy.RESTProxyError(nuage_np_net.error_msg)
    if response[3]:
        pubnet_id = response[3][0]['ID']

    if pubnet_id:
        return pubnet_id

    response = restproxy_serv.rest_call(
        'POST',
        nuage_np_net.post_resource(),
        nuage_np_net.post_data())
    if not nuage_np_net.validate(response):
        if response[0] != constants.CONFLICT_ERR_CODE:
            raise restproxy.RESTProxyError(nuage_np_net.error_msg)
        else:
            response = restproxy_serv.rest_call(
                'GET',
                nuage_np_net.get_resource(), '')
            LOG.debug(nuage_np_net.error_msg)
    return nuage_np_net.get_np_network_id(response)
