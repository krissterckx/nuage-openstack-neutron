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
from neutron._i18n import _
from neutron.callbacks import events
from neutron.callbacks import registry
from neutron.callbacks import resources
from neutron.db.common_db_mixin import CommonDbMixin
from neutron.extensions import securitygroup as ext_sg
from neutron.manager import NeutronManager
from oslo_log import helpers as log_helpers
from oslo_log import log as logging
from oslo_utils import excutils

from nuage_neutron.plugins.common import base_plugin
from nuage_neutron.plugins.common import constants
from nuage_neutron.plugins.common import exceptions as nuage_exc
from nuage_neutron.plugins.common import utils as nuage_utils


LOG = logging.getLogger(__name__)


class NuageSecurityGroup(base_plugin.BaseNuagePlugin,
                         CommonDbMixin):
    def __init__(self):
        super(NuageSecurityGroup, self).__init__()
        self._l2_plugin = None

    @property
    def core_plugin(self):
        if self._l2_plugin is None:
            self._l2_plugin = NeutronManager.get_plugin()
        return self._l2_plugin

    def register(self):
        self.nuage_callbacks.subscribe(self.post_port_create,
                                       resources.PORT, constants.AFTER_CREATE)
        self.nuage_callbacks.subscribe(self.post_port_update,
                                       resources.PORT, constants.AFTER_UPDATE)
        self.nuage_callbacks.subscribe(self.post_port_delete,
                                       resources.PORT, constants.AFTER_DELETE)
        registry.subscribe(self.pre_delete_security_group,
                           resources.SECURITY_GROUP,
                           events.BEFORE_DELETE)
        registry.subscribe(self.pre_create_security_group_rule,
                           resources.SECURITY_GROUP_RULE,
                           events.BEFORE_CREATE)
        registry.subscribe(self.post_create_security_group_rule,
                           resources.SECURITY_GROUP_RULE,
                           events.AFTER_CREATE)
        registry.subscribe(self.pre_delete_security_group_rule,
                           resources.SECURITY_GROUP_RULE,
                           events.BEFORE_DELETE)

    @nuage_utils.handle_nuage_api_error
    @log_helpers.log_method_call
    def pre_delete_security_group(self, resource, event, trigger, **kwargs):
        self.nuageclient.delete_nuage_secgroup(kwargs['security_group_id'])

    @nuage_utils.handle_nuage_api_error
    @log_helpers.log_method_call
    def pre_create_security_group_rule(self, resource, event, trigger,
                                       **kwargs):
        self.nuageclient.validate_nuage_sg_rule_definition(
            kwargs['security_group_rule'])

    @nuage_utils.handle_nuage_api_error
    @log_helpers.log_method_call
    def post_create_security_group_rule(self, resource, event, trigger,
                                        **kwargs):
        remote_sg = None
        context = kwargs['context']
        sg_rule = kwargs['security_group_rule']
        sg_id = sg_rule['security_group_id']

        if sg_rule.get('remote_group_id'):
            remote_sg = self.core_plugin.get_security_group(
                context, sg_rule.get('remote_group_id'))
        try:
            nuage_policygroup = self.nuageclient.get_sg_policygroup_mapping(
                sg_id)
            if nuage_policygroup:
                sg_params = {
                    'sg_id': sg_id,
                    'neutron_sg_rule': sg_rule,
                    'policygroup': nuage_policygroup
                }
                if remote_sg:
                    sg_params['remote_group_name'] = remote_sg['name']
                self.nuageclient.create_nuage_sgrule(sg_params)
        except Exception:
            with excutils.save_and_reraise_exception():
                self.core_plugin.delete_security_group_rule(context,
                                                            sg_rule['id'])

    @nuage_utils.handle_nuage_api_error
    @log_helpers.log_method_call
    def pre_delete_security_group_rule(self, resource, event, trigger,
                                       **kwargs):
        context = kwargs['context']
        id = kwargs['security_group_rule_id']
        local_sg_rule = self.core_plugin.get_security_group_rule(context, id)
        self.nuageclient.delete_nuage_sgrule([local_sg_rule])

    def post_port_create(self, resource, event, trigger, **kwargs):
        context = kwargs['context']
        port = kwargs['port']
        subnet_mapping = kwargs['subnet_mapping']
        if subnet_mapping['nuage_managed_subnet']:
            return

        vsd_subnet = self.nuageclient.get_subnet_or_domain_subnet_by_id(
            subnet_mapping['nuage_subnet_id'])
        if port[ext_sg.SECURITYGROUPS]:
            self._process_port_security_group(context,
                                              port,
                                              kwargs['vport'],
                                              port[ext_sg.SECURITYGROUPS],
                                              vsd_subnet)
        else:
            self._process_port_create_secgrp_for_no_port_sec(port,
                                                             subnet_mapping)

    def post_port_update(self, resource, event, trigger, **kwargs):
        context = kwargs['context']
        updated_port = kwargs['updated_port']
        original_port = kwargs['original_port']
        rollbacks = kwargs['rollbacks']
        subnet_mapping = kwargs['subnet_mapping']
        if subnet_mapping['nuage_managed_subnet']:
            return

        vsd_subnet = self.nuageclient.get_subnet_or_domain_subnet_by_id(
            subnet_mapping['nuage_subnet_id'])
        self._process_port_security_group(context,
                                          updated_port,
                                          kwargs['vport'],
                                          updated_port[ext_sg.SECURITYGROUPS],
                                          vsd_subnet)
        rollbacks.append((self._process_port_security_group,
                          [context, updated_port, kwargs['vport'],
                           original_port[ext_sg.SECURITYGROUPS], vsd_subnet],
                          {}))
        deleted_sg_ids = (set(original_port[ext_sg.SECURITYGROUPS]) -
                          set(updated_port[ext_sg.SECURITYGROUPS]))
        self.nuageclient.check_unused_policygroups(deleted_sg_ids)

    def post_port_delete(self, resource, event, trigger, **kwargs):
        port = kwargs['port']
        subnet_mapping = kwargs['subnet_mapping']
        if subnet_mapping['nuage_managed_subnet']:
            return

        securitygroups = port.get(ext_sg.SECURITYGROUPS, [])
        self.nuageclient.check_unused_policygroups(securitygroups)

    @log_helpers.log_method_call
    def _process_port_security_group(self, context, port, vport, sg_ids,
                                     vsd_subnet):
        if len(sg_ids) > 6:
            msg = (_("Exceeds maximum num of security groups on a port "
                     "supported on nuage VSP"))
            raise nuage_exc.NuageBadRequest(msg=msg)

        if not port.get('fixed_ips'):
            return
        policygroup_ids = []
        for sg_id in sg_ids:
            sg = self.core_plugin._get_security_group(context, sg_id)
            sg_rules = self.core_plugin.get_security_group_rules(
                context,
                {'security_group_id': [sg_id]})
            sg_params = {
                'vsd_subnet': vsd_subnet,
                'sg': sg,
                'sg_rules': sg_rules
            }
            vsd_policygroup_id = (
                self.nuageclient.process_port_create_security_group(
                    sg_params))
            policygroup_ids.append(vsd_policygroup_id)

        self.nuageclient.update_vport_policygroups(vport['ID'],
                                                   policygroup_ids)

    @log_helpers.log_method_call
    def _process_port_create_secgrp_for_no_port_sec(self, port,
                                                    subnet_mapping):
        l2dom_id = None
        l3dom_id = None
        rtr_id = None
        policygroup_ids = []
        port_id = port['id']

        if subnet_mapping:
            if subnet_mapping['nuage_l2dom_tmplt_id']:
                l2dom_id = subnet_mapping['nuage_subnet_id']
            else:
                l3dom_id = subnet_mapping['nuage_subnet_id']
                rtr_id = (self.nuageclient.
                          get_nuage_domain_id_from_subnet(l3dom_id))

            params = {
                'neutron_port_id': port_id,
                'l2dom_id': l2dom_id,
                'l3dom_id': l3dom_id,
                'rtr_id': rtr_id,
                'type': constants.VM_VPORT,
                'sg_type': constants.SOFTWARE
            }
            nuage_port = self.nuageclient.get_nuage_vport_for_port_sec(params)
            if nuage_port:
                nuage_vport_id = nuage_port.get('ID')
                sg_id = (self.nuageclient.
                         create_nuage_sec_grp_for_port_sec(params))
                if sg_id:
                    params['sg_id'] = sg_id
                    (self.nuageclient.
                     create_nuage_sec_grp_rule_for_port_sec(params))
                    policygroup_ids.append(sg_id)
                    self.nuageclient.update_vport_policygroups(
                        nuage_vport_id, policygroup_ids)