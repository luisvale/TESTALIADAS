# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)


class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    user_ids = fields.Many2many('res.users', string='Usuarios')
    analytic_account_id = fields.Many2one('account.analytic.account', 'Cuenta analítica')
    is_start = fields.Boolean(string='Es inicio')


COMB_TYPE = [('category', 'Categoría'),
             ('classification', 'Clasificación'),
             ('meter', 'Metraje'),
             ]

class ProductPricelistItem(models.Model):
    _inherit = 'product.pricelist.item'

    combination_type = fields.Selection(COMB_TYPE, string='Tipo Combinación')
    category_add_id = fields.Many2one('product.category', string='Categoría')
    meter_init = fields.Float(string='Metraje inicio')
    meter_end = fields.Float(string='Metraje fin')
    classification_id = fields.Many2one('product.classification', string='Clasificación')




