# -*- coding: utf-8 -*-
from functools import partial

from odoo import _, fields, models, api
from odoo.exceptions import ValidationError, UserError
import requests
from datetime import datetime, date
import re
import logging
_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _name = "res.users"
    _inherit = "res.users"

    analytic_ids = fields.One2many('res.user.analytic', 'user_id')

    @api.constrains('analytic_ids')
    def _constrains_analytic_ids(self):
        for record in self:
            a_ids = record.analytic_ids.filtered(lambda a: a.default)
            if len(a_ids.ids) > 1:
                raise ValidationError(_("Solo puede tener una cuenta analítca predeterminada."))


class ResUsersAnalytics(models.Model):
    _name = 'res.user.analytic'
    _rec_name = 'analytic_id'

    user_id = fields.Many2one('res.users')
    analytic_id = fields.Many2one('account.analytic.account', string='Analítica')
    default = fields.Boolean(string='Predeterminada')



