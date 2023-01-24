# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime, time

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class MaintenanceLevel(models.Model):
    _name = "maintenance.level"
    _description = 'Aliadas : Niveles de Mantenimiento '
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence asc'
    _rec_name = 'name'

    sequence = fields.Integer(default=1)
    name = fields.Char(string='Nombre')
    active = fields.Boolean(string='Activo')