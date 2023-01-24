# -*- coding: utf-8 -*-

import ast

from datetime import date, datetime, timedelta

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT

class MaintenanceEquipmentTonnage(models.Model):
    _name = 'maintenance.equipment.tonnage'
    _description = 'Tonelaje de equipos de mant.'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    size = fields.Float(string='Tamaño', required=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', required=True, default=lambda self: self.env.company.currency_id.id)
    price = fields.Monetary(string='Precio', default=0.0)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, string='Compañía')

    def name_get(self):
        result = []
        for record in self:
            result.append((record.id, '%s TN' % record.size))
        return result