# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json
import logging
import math
import re
import time
from lxml import etree
from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    customer_bank_id = fields.Many2one('res.partner.bank', string='Banco origen')
    pay_method_id = fields.Many2one('payment.method', string='Método de pago')
    pay_method_code = fields.Char(related='pay_method_id.sequence')
    code_paycheck = fields.Char(string='Código cheque')

    def get_residual_by_invoice(self, inv):
        self.ensure_one()
        #reconciled_invoice_ids = pay.reconciled_invoice_ids

        invoice_payments_widget = inv.invoice_payments_widget
        paid = ''
        if invoice_payments_widget:
            result = json.loads(invoice_payments_widget)
            pay = False
            paid = False
            residual_last = False
            residual = False
            if result:
                for content in result['content']:
                    if content['account_payment_id'] == self.id:
                        pay = content

            if pay:
                if self.currency_id != inv.currency_id:
                    partial_id = self.env['account.partial.reconcile'].sudo().browse(pay['partial_id'])
                    if inv.currency_id == partial_id.debit_currency_id:
                        paid = '(%s %s) %s %s' % (partial_id.debit_currency_id.symbol, partial_id.debit_amount_currency, partial_id.credit_currency_id.symbol, partial_id.credit_amount_currency)
                    else:
                        paid = '(%s %s) %s %s' % (pay['currency'], partial_id.amount, partial_id.credit_currency_id.symbol, partial_id.credit_amount_currency)
                    residual_last = inv.amount_residual + round(pay['amount'], pay['digits'][1] if 'digits' in pay else 2)
                    residual = inv.amount_residual
                else:
                    paid = '%s %s' % (pay['currency'], round(pay['amount'], pay['digits'][1] if 'digits' in pay else 2))
                    residual_last = inv.amount_residual + round(pay['amount'], pay['digits'][1] if 'digits' in pay else 2)
                    residual = inv.amount_residual




            reconciled_invoices_partials = inv._get_reconciled_invoices_partials()
            for r in reconciled_invoices_partials:
                a = r
                b=1

        """SALDOS"""
        return {
            'paid': paid,
            'residual_last': residual_last,
            'residual': residual,
        }

    def get_amount_text(self):
        self.ensure_one()
        amount_text = self.currency_id.amount_to_text_custom(abs(self.amount))
        return amount_text

    def get_amount_text_custom(self):
        self.ensure_one()
        amount_text, currency_name = self.currency_id.amount_to_text_custom(abs(self.amount))
        return [amount_text, currency_name]
