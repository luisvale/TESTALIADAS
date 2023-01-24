# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from datetime import date, datetime, timedelta
import traceback

from ast import literal_eval
from collections import Counter
from dateutil.relativedelta import relativedelta
from markupsafe import Markup
from uuid import uuid4

from odoo import api, fields, models, Command, _, SUPERUSER_ID
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from odoo.tools import format_date, is_html_empty, config
from odoo.tools.float_utils import float_is_zero

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

STATE_NEW_LINE = [('new', 'Nuevo'), ('approved', 'Aprobada')]

class SaleSubscriptionLine(models.Model):
    _inherit = "sale.subscription.line"

    order_line_id = fields.Many2one('sale.order.line')
    amount_consumption = fields.Float(string='Consumo')
    amount_sale = fields.Float(string='Ventas')
    amount_min = fields.Float(string='Mínimo')
    amount_max = fields.Float(string='Máximo')
    percentage_sale = fields.Float(string='% sobre venta', help='Porcentaje sobre venta')
    rental_type = fields.Selection(RENTAL_TYPE, string='Variable')
    date_init = fields.Date(string='Inicio facturación')  # Fecha desde la cual inicia la próxima facturación
    date_end = fields.Date(string='Fin facturación')  # Fecha desde la cual inicia la próxima facturación
    document_type_sale_id = fields.Many2one('document.type', domain=[('in_sale', '=', True)], string='Tipo doc.')
    currency_pricelist = fields.Many2one('res.currency', string='Moneda tarifa')
    currency_external_id = fields.Many2one('res.currency', string='Facturar en')
    currency_rate = fields.Float(store=True, string='T.Cambio', compute='_compute_currency_rate')  # TIPO DE CAMBIO
    amount_convert = fields.Monetary(string='A Facturar', store=True, compute='_compute_amount_convert')
    # pending_amount = fields.Monetary(string='Monto pendiente', compute='_compute_pending_amount')
    pending_amount = fields.Monetary(string='Monto pendiente', compute='_compute_amount')

    pickup_start = fields.Date(string='F.Inicio')
    pickup_end = fields.Date(string='F.Final')

    tax_ids = fields.Many2many('account.tax', string='Impuestos', domain=[('type_tax_use', '=', 'sale')])
    tax_amount = fields.Monetary(string='T.impuesto',compute='_compute_total_subscription')
    total_subscription = fields.Monetary(string='Total', compute='_compute_total_subscription')

    approved_state = fields.Selection(STATE_NEW_LINE, string='Estado', default='approved')

    @api.depends('quantity', 'discount', 'price_unit', 'analytic_account_id.pricelist_id', 'uom_id', 'company_id', 'amount_consumption', 'amount_sale',
                 'percentage_sale', 'amount_min', 'amount_max')
    def _compute_amount(self):
        """
        Compute the amounts of the Subscription line.
        """
        fpos_obj = self.env['account.fiscal.position']
        for line in self:
            partner = line.analytic_account_id.partner_id
            fpos = fpos_obj.with_company(line.analytic_account_id.company_id).get_fiscal_position(
                partner.id)
            tax = line.product_id.sudo().taxes_id
            if fpos:
                tax = fpos.map_tax(line.product_id.sudo().taxes_id)
            price = tax.compute_all(line.price_unit, line.analytic_account_id.currency_id, line.quantity, line.product_id, partner)['total_excluded']
            price_subtotal = price * (100.0 - line.discount) / 100.0
            if line.analytic_account_id.pricelist_id.sudo().currency_id:
                price_subtotal = line.analytic_account_id.pricelist_id.sudo().currency_id.round(price_subtotal)

            # Evaliación de montos 08-11-2022
            rental_type = line.rental_type
            price_subtotal = line._eval_min_max(rental_type, price, price_subtotal)
            line.price_subtotal = price_subtotal
            line.pending_amount = line._compute_pending_amount()

    def _eval_min_max(self, rental_type, price, price_subtotal):
        amount = price_subtotal
        if rental_type == 'fixed':
            amount = 1 * price
        elif rental_type == 'consumption':
            amount = self.amount_consumption * price
        elif rental_type == 'consumption_min':
            value = self.amount_consumption * price
            if self.amount_min > 0.0 and self.amount_max == 0.0:
                if value <= self.amount_min:
                    amount = self.amount_min
                else:
                    amount = value
            elif self.amount_max > 0.0 and self.amount_min == 0.0:
                if value >= self.amount_max:
                    amount = self.amount_max
                else:
                    amount = value
            else:
                amount = value
        elif rental_type == 'consumption_fixed':
            value = self.amount_min if self.amount_min > 0.0 else self.amount_max
            amount = self.amount_consumption * price + value

        # TODO: PAra rentas no tomar en cuenta la cantidad de la subscripción
        elif rental_type == 'rental_min':  # Renta con monto fijo
            if self.amount_sale > 0.0:
                result = round(self.amount_sale * (self.percentage_sale / 100), 2)
                if result > self.amount_min:
                    self.price_unit = result
                else:
                    self.price_unit = self.amount_min
            else:
                self.price_unit = self.amount_min
            amount = self.price_unit * 1

        elif rental_type == 'rental_percentage':  # Renta sobre ventas
            self.price_unit = round(self.amount_sale * (self.percentage_sale / 100), 2)
            amount = self.price_unit * 1

        elif rental_type == 'rental_percentage_top':  # Renta con tope
            if self.amount_sale > 0.0:
                result = round(self.amount_sale * (self.percentage_sale / 100), 2)
                if result >= self.amount_max:
                    self.price_unit = self.amount_max
                elif result <= self.amount_min:
                    self.price_unit = self.amount_min
                else:
                    self.price_unit = result
            else:
                if self.amount_min > 0.0:
                    self.price_unit = self.amount_min
                elif self.amount_max > 0.0:
                    self.price_unit = self.amount_max
                else:
                    self.price_unit = self.amount_sale

            amount = self.price_unit * 1

        return amount

    @api.depends('currency_external_id')
    def _compute_currency_rate(self):
        for record in self:
            currency_rate = 1
            if record.company_id.currency_id != record.currency_external_id:
                currency_rate = record.currency_external_id._convert(1, record.company_id.currency_id, record.company_id, datetime.now().date())
            # if record.currency_id != record.currency_external_id:
            #     currency_rate = record.currency_external_id._convert(currency_rate, record.currency_id, record.company_id, datetime.now().date())
            record.currency_rate = currency_rate

    @api.depends('currency_rate', 'price_subtotal', 'currency_external_id')
    def _compute_amount_convert(self):
        for record in self:
            amount_convert = record.price_subtotal
            if record.currency_id != record.currency_external_id:
                amount_convert = record.currency_id._convert(amount_convert, record.currency_external_id, record.company_id, datetime.now().date())
            record.amount_convert = amount_convert

    # @api.depends('price_subtotal')
    def _compute_pending_amount(self):
        record = self
        pending_amount = 0.0
        subscription = record.analytic_account_id
        recurring_next_date = subscription.recurring_next_date
        if not subscription._filtered_local(record):
            lines, pending_invoiced = record._find_move_line(subscription, recurring_next_date)
            if lines and not pending_invoiced:
                for l in lines:
                    if l.currency_id != subscription.currency_id:
                        if record.price_subtotal > l.credit and record.amount_convert > l.price_unit:
                            pending_amount += record.amount_convert - l.price_unit
                    else:
                        if record.price_subtotal > l.price_unit:
                            pending_amount += record.price_subtotal - l.price_unit
        return pending_amount

    def _find_move_line(self, subscription_id, recurring_next_date):
        pending_invoiced = False
        move_lines = self.env['account.move.line'].sudo()
        lines = self.env['account.move.line'].sudo().search([('subscription_id', 'in', subscription_id.ids),
                                                             ('subscription_next_invoiced', '=', recurring_next_date)],
                                                            order='id desc')
        if lines and len(self.ids)>0:
            move_lines = lines.filtered(lambda l: self.ids[0] in l.subscription_line_ids.ids)
            pending_invoiced = move_lines.filtered(lambda l: l.subscription_is_pending)
        return move_lines, pending_invoiced

    def view_move_lines(self):
        lines = self.env['account.move.line'].sudo().search([('subscription_id', 'in', self.analytic_account_id.ids)], order='id desc')
        move_lines = lines.filtered(lambda l: self.ids[0] in l.subscription_line_ids.ids)
        if move_lines:
            return {
                'name': _('Facturación'),
                'view_mode': 'list',
                'res_model': 'account.move.line',
                # 'view_id': self.env.ref('bpc_aliadas.move_line_history_tree').id,
                'views': [(self.env.ref('bpc_aliadas.move_line_history_tree').id, 'list')],
                'type': 'ir.actions.act_window',
                'target': 'current',
                'domain': [('id', 'in', move_lines.ids)],
                'context': {'expand': True, 'create': False, 'fsm_mode': True}
            }

    def view_product_id(self):
        if self.product_id:
            return {
                'name': self.product_id.display_name,
                'type': 'ir.actions.act_window',
                'res_model': 'product.product',
                'views': [(self.env.ref('product.product_normal_form_view').id, 'form')],
                'target': 'current',
                'res_id': self.product_id.id,
                #'domain': [('id', '=', self.product_id.id)],
                'context': {'expand': True, 'create': False, 'fsm_mode': True}
            }

    @api.depends('tax_ids', 'price_subtotal', 'product_id')
    def _compute_total_subscription(self):
        for record in self:
            total_subscription = 0.0
            tax_amount = 0.0
            if record.tax_ids:
                for tax_id in record.tax_ids:
                    taxes = tax_id.compute_all(record.price_subtotal, record.currency_id, 1, product=record.product_id, partner=record.analytic_account_id.partner_id)
                    total_subscription += taxes['total_included']
                    tax_amount += (taxes['total_included'] - record.price_subtotal)
                    # a = 1
            else:
                total_subscription = record.price_subtotal
            record.tax_amount = tax_amount
            record.total_subscription = total_subscription

    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id.id == self.env.ref('bpc_aliadas.rental_product_bpc').id and not self.env.user.user_has_groups('bpc_aliadas.group_aliadas_sale_subs_product_rent_default'):
            raise ValidationError(_("No tiene permiso para seleccionar este producto."))
        super(SaleSubscriptionLine, self).onchange_product_id()
        self._search_product_in_line_order(self)

    def _search_product_in_line_order(self, line):
        line.approved_state = 'new'
