# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, date
import json


class AccountAccount(models.Model):
    _inherit = 'account.account'

    active = fields.Boolean(default=True, string='Activo')
