# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime, time

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class PurchaseRequisition(models.Model):
    _inherit = "purchase.requisition"

    # P1 = Proceso 1, P2 = Proceso 2
    get_purchase = fields.Boolean(compute='_compute_get_purchase') #P1
    purchase_line_ids = fields.Many2many('purchase.order') #P1
    purchase_order_line_ids = fields.Many2many('purchase.order.line', compute='_compute_purchase_order_line_ids', store=True, readonly=False)
    automatic = fields.Boolean('Automático', help='Se creo automáticamente por medio de un producto requerido', store=True, readonly=True) #P2
    request_id = fields.Many2one('approval.request', compute='_compute_request_id', string='Solicitud', store=True, readonly=False)
    department_id = fields.Many2one('hr.department', string='Departamento')

    def _compute_request_id(self):
        for record in self:
            if record.request_id:
                request_id = record.request_id
            else:
                request_id = record.env['approval.request'].sudo().search([('requisition_id','in',record.ids)], limit=1)
            record.request_id = request_id



    @api.model
    def _domain_analytic(self):
        analytic_ids = self.env.user.analytic_ids
        a_ids = analytic_ids.mapped('analytic_id')
        return [('id', 'in', a_ids.ids)]

    def _default_analytic(self):
        analytic_ids = self.env.user.analytic_ids
        a_ids = analytic_ids.filtered(lambda a: a.default)
        if a_ids:
            return a_ids.analytic_id
        else:
            return False

    analytic_account_id = fields.Many2one('account.analytic.account', domain=_domain_analytic, default=_default_analytic)

    @api.depends('purchase_ids','purchase_ids.state')
    def _compute_get_purchase(self):
        for record in self:
            get_purchase = False
            if record.purchase_ids:
                get_purchase = True
                for po in record.purchase_ids:
                    record.purchase_line_ids += po

            record.get_purchase = get_purchase

    def _find_requisition_by_product(self, product_id, company_id):
        lines = self.env['purchase.requisition.line'].sudo().search([('product_id', '=', product_id),
                                                                    ('requisition_id.state', 'not in', ('done', 'cancel')),
                                                                    ('company_id', '=', company_id)])

        if lines:
            for l in lines:
                _logger.info("ALIDAS: Producto con ID %s en línea %s de la licitación %s" % (product_id, l.id, l.requisition_id.name))
        return lines


    @api.onchange('analytic_account_id')
    def _onchange_analytic_account_id(self):
        for record in self:
            if record.line_ids and record.analytic_account_id:
                for line in record.line_ids:
                    line.sudo().write({'account_analytic_id': record.analytic_account_id.id})

    @api.depends('purchase_line_ids')
    def _compute_purchase_order_line_ids(self):
        for record in self:
            purchase_order_line_ids = False
            if record.purchase_line_ids:
                purchase_order_line_ids = record.purchase_line_ids.mapped('order_line')
            record.purchase_order_line_ids = purchase_order_line_ids



class PurchaseRequisitionLine(models.Model):
    _inherit = "purchase.requisition.line"

    account_id = fields.Many2one('account.account', string='Cuenta')

    def _prepare_purchase_order_line(self, name, product_qty=0.0, price_unit=0.0, taxes_ids=False):
        res = super(PurchaseRequisitionLine, self)._prepare_purchase_order_line(name, product_qty, price_unit, taxes_ids)
        if self.account_id:
            res['account_id'] = self.account_id.id
        # if self.product_description_variants:
        #     res['name'] = self.product_description_variants
            #res['name'] = name
        return res

    @api.depends('product_id', 'schedule_date')
    def _compute_account_analytic_id(self):
        super(PurchaseRequisitionLine, self)._compute_account_analytic_id()
        for line in self:
            if line.requisition_id:
                line.account_analytic_id = line.requisition_id.analytic_account_id

    @api.onchange('product_id')
    def _onchange_product_id(self):
        super(PurchaseRequisitionLine, self)._onchange_product_id()
        for record in self:
            if record.product_id:
                accounts = self.product_id.product_tmpl_id.get_product_accounts()
                account_id = accounts['expense']
                record.account_id = account_id
            else:
                record.account_id = False


