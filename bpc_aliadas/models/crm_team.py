# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, date


class CrmTeam(models.Model):
    _inherit = 'crm.team'

    not_project = fields.Boolean(string='Crear proyecto manual',
                                 help='Esto impide que el proyecto se cree de la forma standard, al contrario será de forma manual')

    authorization_payment_term = fields.Boolean(string='Autorización de plazo de pago')

    hide_columns_mim_max = fields.Boolean(string='Ocultar mínimos y máximos', help='Ocultar columnas mínimo y máximo en orden de venta.')
