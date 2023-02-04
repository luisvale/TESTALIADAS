from odoo import api, fields, models,exceptions


class AccountInvoice(models.Model):
    _inherit = "account.move"

    cancel_paid_invoice = fields.Boolean(string='Cancel Paid Invoice?', compute='check_cancel_paid_invoice')

    def check_cancel_paid_invoice(self):

        for invoice in self:
            if invoice.company_id.cancel_paid_invoice:
                invoice.cancel_paid_invoice = True
            else:
                invoice.cancel_paid_invoice = False
    
    def button_cancel(self):
        for invoice in self:
            if invoice.company_id.cancel_paid_invoice:
                # if invoice.journal_id and not invoice.journal_id.restrict_mode_hash_table:
                #     invoice.journal_id.write({'restrict_mode_hash_table':True})
                # payment_move = invoice.payment_id.move_id
                payment_move_lines = invoice.payment_id.move_id.mapped('line_ids')
                if payment_move_lines:
                    payment_move_lines.remove_move_reconcile()
                    # payment_move.button_cancel()
                    invoice.payment_id.action_draft()
        res = super(AccountInvoice,self).button_cancel()
        return res

    def unlink(self):
        return super(AccountInvoice, self.with_context(force_delete=True)).unlink()
