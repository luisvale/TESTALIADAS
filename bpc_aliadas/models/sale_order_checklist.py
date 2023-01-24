# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime, time

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class SaleOrderChecklist(models.Model):
    _name = "sale.order.check_list"
    _description = 'Chek list en ordenes de venta'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence desc'
    _rec_name = 'name'

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    sequence = fields.Integer(string='Secuencia', required=True)
    name = fields.Char(string='Nombre', required=True)
    description = fields.Text(string='Descripción')
    state_active = fields.Boolean(default=True, string='Activo')

