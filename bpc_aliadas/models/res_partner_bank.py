# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, date
import json

class ResBank(models.Model):
    _inherit = 'res.bank'

    aba = fields.Char(string='ABA')


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    bank_bic_id = fields.Char(related='bank_id.bic', string='SWIFT', readonly=False)
    bank_aba_id = fields.Char(related='bank_id.aba', string='ABA', readonly=False)
    bank_address_id = fields.Char(compute='_compute_bank_address_id', string='Dirección')
    bank_intermediary = fields.Many2one('res.bank', string='Banco intermediario')
    bank_intermediary_address = fields.Char(compute='_compute_bank_intermediary_address', string='Dirección B.Int.')
    bank_direct = fields.Many2one('res.bank', string='Banco directo')
    bank_direct_address = fields.Char(compute='_compute_bank_direct_address', string='Dirección B.Dir.')

    @api.depends('bank_intermediary')
    def _compute_bank_intermediary_address(self):
        for record in self:
            bank_intermediary_address = False
            if record.bank_intermediary:
                address = []
                if record.bank_intermediary.street:
                    address.append(record.bank_intermediary.street)
                if record.bank_intermediary.city:
                    address.append(record.bank_intermediary.city)
                if record.bank_intermediary.state:
                    address.append(record.bank_intermediary.state.name)
                if record.bank_intermediary.country:
                    address.append(record.bank_intermediary.country.name)

                bank_intermediary_address = ','.join(address)

            record.bank_intermediary_address = bank_intermediary_address

    @api.depends('bank_direct')
    def _compute_bank_direct_address(self):
        for record in self:
            bank_direct_address = False
            if record.bank_intermediary:
                address = []
                if record.bank_direct.street:
                    address.append(record.bank_direct.street)
                if record.bank_direct.city:
                    address.append(record.bank_direct.city)
                if record.bank_direct.state:
                    address.append(record.bank_direct.state.name)
                if record.bank_direct.country:
                    address.append(record.bank_direct.country.name)

                bank_direct_address = ','.join(address)

            record.bank_direct_address = bank_direct_address

    @api.depends('bank_id')
    def _compute_bank_address_id(self):
        for record in self:
            bank_address = False
            if record.bank_id:
                address = []
                if record.bank_id.street:
                    address.append(record.bank_id.street)
                if record.bank_id.city:
                    address.append(record.bank_id.city)
                if record.bank_id.state:
                    address.append(record.bank_id.state.name)
                if record.bank_id.country:
                    address.append(record.bank_id.country.name)

                bank_address = ','.join(address)

            record.bank_address_id = bank_address







