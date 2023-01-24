# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime, time
from dateutil.relativedelta import relativedelta
from functools import partial
from itertools import groupby
import json

from markupsafe import escape, Markup
from pytz import timezone, UTC
from werkzeug.urls import url_encode
from collections import defaultdict

from odoo import api, fields, models, _, SUPERUSER_ID
from odoo.osv import expression
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.misc import formatLang, get_lang, format_amount
from odoo.tests.common import TransactionCase, tagged, Form

import logging

_logger = logging.getLogger(__name__)


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    amount_total_order = fields.Monetary(string='Total orden', store=True, related='order_id.amount_total', readonly=False)
    account_id = fields.Many2one('account.account', string='Cuenta contable')
    limit_budget = fields.Boolean(help='Paso el límite de prespuesto', copy=False)
    is_downpayment = fields.Boolean(string="Is a down payment", help="Down payments are made when creating invoices from a sales order."
                                                                     " They are not copied when duplicating a sales order.")
    brand_name = fields.Char(string='Marca')
    check_purchase = fields.Boolean(help='Check que permite saber que productos se le van a comprar al proveedor')
    is_advance = fields.Boolean(string='Es anticipo', related='product_id.is_advance')


    @api.onchange('product_id')
    def onchange_product_id(self):
        super(PurchaseOrderLine, self).onchange_product_id()
        if self.product_id:
            accounts = self.product_id.product_tmpl_id.get_product_accounts()
            account_id = accounts['expense']
            self.account_id = account_id

    def _prepare_account_move_line(self, move=False):
        res = super(PurchaseOrderLine, self)._prepare_account_move_line(move)
        if self.account_id:
            res['account_id'] = self.account_id.id
        return res


    def _create_stock_moves(self, picking):
        values = []

        lines_to_moves = self.filtered(lambda l: l.check_purchase)
        if not lines_to_moves:
            raise ValidationError(_("No hay niguna línea seleccionada para la generación del picking"))

        for line in self.filtered(lambda l: not l.display_type and l.check_purchase):
            for val in line._prepare_stock_moves(picking):
                values.append(val)
            line.move_dest_ids.created_purchase_line_id = False

        return self.env['stock.move'].create(values)

    @api.onchange('check_purchase')
    def _onchange_check_purchase(self):
        for record in self:
            _logger.info("Evaluando check_purchase")
            if record.check_purchase and record.product_id:
                if record.is_advance:
                    continue
                requisition_id = record.order_id.requisition_id
                line_requisition = requisition_id.line_ids.filtered(lambda l: l.product_id.id == record.product_id.id)
                for r_line in line_requisition:
                    qty_total = r_line.product_qty
                    qty = record.product_qty
                    purchase_o_ids = record.order_id.purchase_o_ids
                    if purchase_o_ids:
                        order_lines = purchase_o_ids.filtered(lambda o: o.state != 'cancel').mapped('order_line')
                        lines_check_product = order_lines.filtered(lambda l: l.product_id.id == record.product_id.id and l.check_purchase
                                                                   and record.account_analytic_id == r_line.account_analytic_id)
                        qty_lines = sum(line.product_qty for line in lines_check_product)
                        qty += qty_lines
                        if qty > qty_total:
                            ca_name = record.account_analytic_id.name if record.account_analytic_id else 'Sin cuenta analítica'
                            raise ValidationError(_("Cuenta analítica %s: El total requerido para el producto %s es de %s. La cantidad en esta orden sumada a "
                                                    "las demas ordenes del acuerdo de compra %s es de %s.  "
                                                    % (ca_name, record.product_id.name, qty_total, requisition_id.name, qty)))

                    #raise ValidationError(_("La selección del producto a comprar ya se hizo en la orden %s " % lines_check_product[0].order_id.name))
