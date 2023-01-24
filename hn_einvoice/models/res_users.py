# -*- coding: utf-8 -*-

from odoo import fields, models, _, api
from odoo.exceptions import UserError,ValidationError

class ResUsers(models.Model):
    _name = "res.users"
    _inherit = "res.users"

    journal_ids = fields.Many2many('account.journal', string='Diarios', domain=[('type', '=', 'sale')])
    journal_id = fields.Many2one('account.journal', string='Diario predeterminado')



