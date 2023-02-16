# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, date
import json
import logging
_logger = logging.getLogger(__name__)


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    note_tag = fields.Many2many('note.tag.bpc', string='Notas')
    rental_type = fields.Selection(string='Variable', related='product_id.rental_type')
    #Historial
    subscription_line_ids = fields.Many2many('sale.subscription.line', help='Líneas subscripción relacionadas')
    subscription_id = fields.Many2one('sale.subscription')
    subscription_contract_name = fields.Char(related='subscription_id.contract_name')
    subscription_period_start = fields.Date(string='Inicio')
    subscription_period_end = fields.Date(string='Fin')
    subscription_next_invoiced = fields.Date(string='Próxima facturación')
    subscription_is_pending = fields.Boolean(help='Cobrado adicional')
    subscription_line_consumption = fields.Float(string='Consumo')
    subscription_line_sale = fields.Float(string='Ventas')
    subscription_line_percentage_sale = fields.Float(string='% sobre venta', help='Porcentaje sobre venta')
    subscription_line_amount_min = fields.Float(string='Mínimo')
    subscription_line_amount_max = fields.Float(string='Máximo')

    subscription_currency_rate = fields.Float(string='T.Cambio', default=1)


    # TODO: Aquí reemplazaremos el tipo de cambio que viene en la subscripción
    @api.model
    def _get_fields_onchange_subtotal_model(self, price_subtotal, move_type, currency, company, date):
        ''' This method is used to recompute the values of 'amount_currency', 'debit', 'credit' due to a change made
        in some business fields (affecting the 'price_subtotal' field).

        :param price_subtotal:  The untaxed amount.
        :param move_type:       The type of the move.
        :param currency:        The line's currency.
        :param company:         The move's company.
        :param date:            The move's date.
        :return:                A dictionary containing 'debit', 'credit', 'amount_currency'.
        '''
        if move_type in self.move_id.get_outbound_types():
            sign = 1
        elif move_type in self.move_id.get_inbound_types():
            sign = -1
        else:
            sign = 1

        amount_currency = price_subtotal * sign
        _next, new_balance = self._apply_new_balance(currency, company, amount_currency, sign)
        if _next:
            balance = new_balance
        else:
            balance = currency._convert(amount_currency, company.currency_id, company, date or fields.Date.context_today(self))
        return {
            'amount_currency': amount_currency,
            'currency_id': currency.id,
            'debit': balance > 0.0 and balance or 0.0,
            'credit': balance < 0.0 and -balance or 0.0,
        }

    def _apply_new_balance(self, currency, company, amount_currency, sign):
        _next = False
        balance = 0
        _logger.info("Evaluación de tipo de cambio de : %s " % self.name)
        if currency != company.currency_id and self.subscription_currency_rate > 0 and self.subscription_id and sign == -1:
            _next = True
            balance = amount_currency * self.subscription_currency_rate
            _logger.info("Balance nuevo : %s " % balance)

        return _next, balance


    def create_analytic_lines(self):
        if not self._find_disabled():
            return super(AccountMoveLine, self).create_analytic_lines()
        else:
            _logger.info("No aplicará líneas analíticas con presupuestos para factura %s " % self[0].move_id.name)

    def _find_disabled(self):
        line = self[0]
        if line.company_id.account_budget_analytic_supplier_disabled and line.move_id.move_type in ['in_invoice','in_refund']:
            return True
        return False