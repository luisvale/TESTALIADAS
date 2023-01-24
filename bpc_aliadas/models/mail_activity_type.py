# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, date


class MailActivityType(models.Model):
    _inherit = 'mail.activity.type'

    model_id = fields.Integer(string='ID registro')
    model_ref = fields.Char('Referencia')