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

    # @api.model
    # def _cron_purchase_requisition_by_product(self):
    #     products = self.sudo().search([('active', '=', True), ('auto_requisition', '=', True), ('purchase_ok', '=', True)])
    #     if products:
    #         for p in products:
    #             seller_ids = p.seller_ids
    #             if seller_ids and p.qty_available <= 0.0:
    #                 _logger.info("ALIADAS: Producto %s con stock en %s - SI procede a creación de licitción" % (p.name, p.qty_available))
    #                 p._create_requisition_by_product()
    #             else:
    #                 _logger.info("ALIADAS: Producto %s con stock en %s - NO procede a creación de licitción" % (p.name, p.qty_available))
    #                 # _logger.info("")
    #
    # def _create_requisition_by_product(self):
    #
    #     requisition_ids = self.env['purchase.requisition'].sudo().search([('automatic', '=', True),
    #                                                                       ('template_id', 'in', self.ids),
    #                                                                       ('state', '!=', 'done')])
    #     if requisition_ids:
    #         for req in requisition_ids:
    #             _logger.info("ALIADAS : Requerimiento automático con ID %s y ESTADO %s" % (req.id, req.state))
    #     else:
    #         points = self.env['stock.warehouse.orderpoint'].sudo().search([('product_tmpl_id', '=', self.id)])
    #         if points:
    #             product_min_qty = points.mapped('product_min_qty')
    #             minimal = min(product_min_qty)
    #             if minimal > 0.0:
    #                 price = sum(seller.price for seller in self.seller_ids) / len(self.seller_ids.ids)
    #
    #                 def _get_lines(self):
    #                     list_lines = [(0, 0, {
    #                         'product_id': self.product_variant_id.id,
    #                         'product_qty': minimal,
    #                         'price_unit': price,
    #                         'product_uom_id': self.uom_po_id.id if self.uom_po_id.id else False
    #                     })]
    #                     return list_lines
    #
    #                 requisition_new = self.env['purchase.requisition'].sudo().create({
    #                     'line_ids': _get_lines(self),
    #                     'user_id': self.env.user.id,
    #                     # 'vendor_id': self.partner_id.id,
    #                     'currency_id': self.env.user.company_id.currency_id.id,
    #                     'ordering_date': datetime.now().date(),
    #                     'automatic': True,
    #                     'template_id': self.id,
    #                 })
    #
    #                 error = False
    #                 for seller in self.seller_ids:
    #                     try:
    #                         purchase_order = self.env['purchase.order'].create({
    #                             'partner_id': seller.name.id,
    #                             'requisition_id': requisition_new.id,
    #                             'order_line': [
    #                                 (0, 0, {
    #                                     'name': self.name,
    #                                     'product_id': self.product_variant_id.id,
    #                                     'product_qty': minimal,
    #                                     'product_uom': self.uom_po_id.id,
    #                                     'price_unit': seller.price,
    #                                     'date_planned': fields.Datetime.now(),
    #                                 })]
    #                         })
    #                         _logger.info("ALIADAS: Orden de comrpa creada ID %s" % purchase_order)
    #                     except Exception as e:
    #                         _logger.info("ALIADAS: Error al crear orden de compra %s " % e)
    #                         error = True
    #
    #                 if error:
    #
    #                     requisition_new.sudo().unlink()
    #                 else:
    #                     requisition_new.sudo().write({'seller_ids': [(6, 0, self.seller_ids.ids)]})
    #                     requisition_new.sudo().action_in_progress()
