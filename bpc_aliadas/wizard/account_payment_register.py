# -*- coding: utf-8 -*-
from collections import defaultdict
from lxml import etree
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, frozendict
import logging
_logger = logging.getLogger(__name__)


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    customer_bank_ids = fields.One2many(related='partner_id.bank_ids', readonly=False)
    customer_bank_id = fields.Many2one('res.partner.bank', string='Banco origen')
    #pay_method_ids = fields.Many2many(related='partner_id.pay_method_ids')

    def _domain_payment(self):
        context = self.env.context
        if 'params' in context:
            params = context['params']
            if 'model' in params and 'id' in params and params['model'] == 'account.move':
                move = self.env[params['model']].sudo().browse(params['id'])
            elif 'active_model' in context and context['active_model'] and 'active_id' in context:
                move = self.env[context['active_model']].sudo().browse(context['active_id'])
            if move:
                partner_id = move.partner_id
                if move.move_type in ('in_invoice','in_refund') and partner_id.pay_method_ids:
                    return [('id', 'in', partner_id.pay_method_ids.ids)]

        return [('id','!=',False)]

    pay_method_id = fields.Many2one('payment.method', string='Método de pago', domain=_domain_payment)

    def _create_payment_vals_from_wizard(self):
        res = super(AccountPaymentRegister, self)._create_payment_vals_from_wizard()
        if self.customer_bank_id:
            res['customer_bank_id'] = self.customer_bank_id.id
        if self.pay_method_id:
            res['pay_method_id'] = self.pay_method_id.id

        return res

    def _create_payment_vals_from_batch(self, batch_result):
        res = super(AccountPaymentRegister, self)._create_payment_vals_from_batch(batch_result)
        if self.pay_method_id:
            res['pay_method_id'] = self.pay_method_id.id
        return res

    def _create_payments(self):
        self.ensure_one()
        batches = self._get_batches()
        edit_mode = self.can_edit_wizard and (len(batches[0]['lines']) == 1 or self.group_payment)
        to_process = []

        if edit_mode:
            payment_vals = self._create_payment_vals_from_wizard()
            to_process.append({
                'create_vals': payment_vals,
                'to_reconcile': batches[0]['lines'],
                'batch': batches[0],
            })
        else:
            # Don't group payments: Create one batch per move.
            if not self.group_payment:
                new_batches = []
                for batch_result in batches:
                    for line in batch_result['lines']:
                        new_batches.append({
                            **batch_result,
                            'payment_values': {
                                **batch_result['payment_values'],
                                'payment_type': 'inbound' if line.balance > 0 else 'outbound'
                            },
                            'lines': line,
                        })
                batches = new_batches

            for batch_result in batches:
                to_process.append({
                    'create_vals': self._create_payment_vals_from_batch(batch_result),
                    'to_reconcile': batch_result['lines'],
                    'batch': batch_result,
                })

        payments = self._init_payments(to_process, edit_mode=edit_mode)
        self._post_payments(to_process, edit_mode=edit_mode)
        self._code_paycheck_generate(payments)
        self._reconcile_payments(to_process, edit_mode=edit_mode)
        return payments


    def _code_paycheck_generate(self, payments):
        check_id = self.env.ref('bpc_aliadas.PaymentMethods_3')
        payments_check = payments.filtered(lambda p: p.pay_method_id.id == check_id.id)
        for pay in payments_check:
            payment_check = self.env.ref('bpc_aliadas.sequence_payment_check')
            code_paycheck = payment_check.next_by_id()
            pay.sudo().write({'code_paycheck': code_paycheck})
            _logger.info("PAYMENT : %s - CODE CHECK %s" % (pay.name, code_paycheck))
