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

    required_authorization = fields.Boolean(string='Requiere autorización')


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
    price_min = fields.Monetary(string='Precio Min.', default=0.0)
    price_max = fields.Monetary(string='Precio Max.', default=0.0)

    @api.constrains('fixed_price', 'price_min', 'price_max')
    def _constraint_prices(self):
        for record in self:
            if not record.price_min <= record.fixed_price <= record.price_max:
                raise ValidationError(_("Los precios deben ir de menor a mayor : Precio mínimo, precio fijo y precio máximo."))

    @api.onchange('fixed_price', 'price_min', 'price_max')
    def _onchange_prices(self):
        for record in self:
            if record.price_min:
                record._find_intervals(record.price_min)
            if record.fixed_price:
                record._find_intervals(record.fixed_price)
            if record.price_max:
                record._find_intervals(record.price_max)

    def _find_intervals(self, price):
        self.ensure_one()
        _finds = self.sudo().search([('pricelist_id', '=', self.pricelist_id.id),
                                     ('pricelist_id.analytic_account_id', '=', self.pricelist_id.analytic_account_id.id),
                                     ('price_min', '>=', price),
                                     ('price_max', '<=', price),
                                     ])
        if _finds:
            raise ValidationError(_("El precio ingresado %s ya se ecuentra registrado en una lista de precios para esta cuenta analítica. "
                                    "Referencia de tarifa encontrada : %s " % (price, _finds[0].pricelist_id.name)))
