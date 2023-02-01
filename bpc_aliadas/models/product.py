# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, date
import logging

_logger = logging.getLogger(__name__)

RENTAL_TYPE = [
    ('fixed', 'Monto fijo'),
    ('m2', 'Monto por metro cuadrado'),
    ('consumption', 'Consumo'),
    ('consumption_min', 'Consumo mínimo'),
    ('consumption_fixed', 'Consumo y monto fijo'),
    ('rental_min', 'Renta monto mínimo'),
    ('rental_percentage', 'Renta % de ventas'),
    ('rental_percentage_top', 'Renta % de ventas con tope'),
    ('tonnage', 'Tonelaje'),
]


class ProductCategory(models.Model):
    _inherit = 'product.category'

    @api.model_create_multi
    def create(self, vals_list):
        for val in vals_list:
            if 'name' in val:
                if val['name']:
                    pts = self.sudo().search([('name', 'ilike', val['name'] + '%')])
                    if pts:
                        for p in pts:
                            if p.name.lower() == val['name'].lower():
                                raise ValidationError(_("Se han encontrado 1 categoría con este mismo nombre"))
        return super(ProductCategory, self).create(vals_list)
        # return res


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    classification_id = fields.Many2one('product.classification', string='Clasificación')
    meter2 = fields.Float(string='Medida arrendada', digits=(16, 4))
    meter_real = fields.Float(string='Medida real', digits=(16, 4))
    rental_type = fields.Selection(RENTAL_TYPE, string='Variable')
    analytic_account_id = fields.Many2one('account.analytic.account', 'Cuenta analítica')
    #auto_requisition = fields.Boolean(string='Auto licitación', help='Genera licitaciones de forma automática, dependiendo de los proveedores')
    document_type_sale_id = fields.Many2one('document.type', domain=[('in_sale', '=', True)], string='Tipo documento')
    is_advance = fields.Boolean(string='Es anticipo')
    warehouse_ids = fields.Many2many('stock.warehouse', string='Almacenes', compute='_compute_location_ids')

    is_free = fields.Boolean(string='Local no totalizado')
    not_total = fields.Boolean(string='No total')

    currency_id = fields.Many2one('res.currency', 'Currency', compute='_compute_currency_id', readonly=False)
    currency_invoice_id = fields.Many2one('res.currency', string='Moneda facturación')


    @api.depends('company_id', 'currency_invoice_id')
    def _compute_currency_id(self):
        main_company = self.env['res.company']._get_main_company()
        for template in self:
            if template.currency_invoice_id:
                template.currency_id = template.currency_invoice_id
            else:
                template.currency_id = template.company_id.sudo().currency_id.id or main_company.currency_id.id

    def _compute_location_ids(self):
        for record in self:
            quants = self.env['stock.quant'].sudo().search([('product_tmpl_id', 'in', record.ids)])
            record.warehouse_ids = quants.mapped('location_id').mapped('warehouse_id')

    @api.model_create_multi
    def create(self, vals_list):
        for val in vals_list:
            if 'name' in val:
                if val['name']:
                    pts = self.sudo().search([('name', 'ilike', val['name'] + '%')])
                    if pts:
                        for p in pts:
                            if p.name.lower() == val['name'].lower():
                                raise ValidationError(_("Se han encontrado 1 producto con este mismo nombre"))
        return super(ProductTemplate, self).create(vals_list)
        #return res
