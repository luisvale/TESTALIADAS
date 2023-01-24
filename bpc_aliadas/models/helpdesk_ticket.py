# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, date


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    contract = fields.Char(string='Contrato', index=True, website_form_blacklisted=False)

    def view_subscription_by_contract(self):
        self.ensure_one()
        if self.contract:
            subcription_id = self.env['sale.subscription'].sudo().search(['|',('name','=',self.contract),('contract_name', '=', self.contract)])
            if subcription_id:
                return {
                    'name': _('Subscripción'),
                    'view_mode': 'form',
                    'res_model': 'sale.subscription',
                    'type': 'ir.actions.act_window',
                    'res_id': subcription_id.id
                }
            else:
                raise ValidationError(_("No se encontró subscripción para número de contrato %s " % self.contract))