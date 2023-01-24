# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, Command, fields, models, _
from collections import defaultdict
from datetime import date, datetime
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)


class ApprovalLevel(models.Model):
    _name = 'approval.level'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Niveles de aprobación'
    _rec_name = 'name'
    _order = 'sequence ASC'

    sequence = fields.Integer(default=1, string='Número')
    name = fields.Char('Nombre', required=True, translate=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, string='Compañía')

    _sql_constraints = [('name_uniq', 'unique (name)', "El nombre ya existe !"),]

