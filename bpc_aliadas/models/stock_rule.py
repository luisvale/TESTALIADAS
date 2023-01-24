# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from datetime import datetime
from dateutil.relativedelta import relativedelta
from itertools import groupby
from odoo.tools import float_compare

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.addons.stock.models.stock_rule import ProcurementException

import logging
_logger = logging.getLogger(__name__)

class StockRule(models.Model):
    _inherit = 'stock.rule'

    @api.model
    def _run_buy(self, procurements):
        requisitions_values_by_company = defaultdict(list)
        other_procurements = []
        for procurement, rule in procurements:
            if procurement.product_id.purchase_requisition == 'tenders':
                values = self.env['purchase.requisition']._prepare_tender_values(*procurement)
                values['picking_type_id'] = rule.picking_type_id.id
                requisitions_values_by_company[procurement.company_id.id].append(values)
            else:
                other_procurements.append((procurement, rule))

        next_process_by_company = defaultdict(list)
        for company_id, requisitions_values in requisitions_values_by_company.items():
            company = self.env['res.company'].sudo().browse(company_id)
            if company.purchase_requisition_group_by:
                next_process_by_company[company_id].append(requisitions_values)
            else:
                self.env['purchase.requisition'].sudo().with_company(company_id).create(requisitions_values)

        if next_process_by_company:
            self._compact_requisition(next_process_by_company)

        return super(StockRule, self)._run_buy(other_procurements)

    def _compact_requisition(self, next_process_by_company):
        for company_id, values_list in next_process_by_company.items():
            company = self.env['res.company'].sudo().browse(company_id)
            product_ids = self.env['product.product'].sudo()
            new_list = defaultdict(list)
            lines_to_requisition = []
            origins = ''
            for value in values_list[0]:
                origins += ('%s /' % value['origin'])
                line_ids = value['line_ids']
                line = line_ids[0][2]
                product = self.env['product.product'].sudo().browse(line['product_id'])
                if not self.env['purchase.requisition'].sudo()._find_requisition_by_product(line['product_id'],company_id):
                    product_ids += product
                    seller_ids = product.product_tmpl_id.seller_ids
                    if seller_ids:
                        #supplier_ids += seller_ids.mapped('name')
                        for seller in seller_ids:
                            data = {
                                'name': product.name,
                                'product_id': line['product_id'],
                                'product_qty': line['product_qty'],
                                'product_uom': line['product_uom_id'],
                                'price_unit': seller.price,
                            }
                            new_list[seller.name.id].append((0,0,data))
                                #new_list.append({'partner': seller.name, 'values': })

                    lines_to_requisition.append(line_ids[0])
                else:
                    _logger.info("ALIADAS: El producto %s se encuentra en uan licitación en proceso " % product.product_tmpl_id.name)

            if new_list:

                requisition_new = self.env['purchase.requisition'].sudo().with_company(company_id).create({
                    'line_ids': lines_to_requisition,
                    #'user_id': self.env.user.id,
                    # 'vendor_id': self.partner_id.id,
                    'currency_id': company.currency_id.id,
                    'ordering_date': datetime.now().date(),
                    'automatic': True,
                    #'template_id': self.id,
                    'origin': origins,
                    'date_end': value['date_end'],
                    'warehouse_id': value['warehouse_id']
                })
                if requisition_new:
                    _logger.info("ALIADAS: Licitacón con ID %s creada" % requisition_new.id)

                    error = False
                    for partner_id, line_ids in new_list.items():
                        try:
                            purchase_order = self.env['purchase.order'].create({
                                'partner_id': partner_id,
                                'requisition_id': requisition_new.id,
                                'order_line': line_ids
                            })
                            _logger.info("ALIADAS: Orden de comrpa creada ID %s" % purchase_order)
                        except Exception as e:
                            _logger.info("ALIADAS: Error al crear orden de compra %s " % e)
                            error = True

                    if error:
                        requisition_new.sudo().unlink()
                    else:
                        requisition_new.sudo().action_in_progress()


