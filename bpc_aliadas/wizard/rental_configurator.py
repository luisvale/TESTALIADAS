# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class RentalWizard(models.TransientModel):
    _inherit = 'rental.wizard'

    pricelist_item_ids = fields.Many2many('product.pricelist.item', compute='_compute_pricelist_item_ids')

    @api.depends('product_id')
    def _compute_pricelist_item_ids(self):
        for record in self:
            pricelist_item_ids = self.env['product.pricelist.item'].sudo()
            if record.product_id:
                product_id = record.product_id
                template_id = record.product_id.product_tmpl_id
                items = record.env['product.pricelist.item'].sudo().search(['|', '|',
                                                                            ('product_tmpl_id', '=', template_id.id),
                                                                            ('product_id', 'in', product_id.ids),
                                                                            ('categ_id', '=', template_id.categ_id.id)
                                                                            ])
                if items:
                    pricelist_item_ids += items

            record.pricelist_item_ids = pricelist_item_ids
