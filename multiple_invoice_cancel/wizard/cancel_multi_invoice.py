from odoo import api, models
class CancelMultiInvoice(models.TransientModel):
    _name = "cancel.multi.invoice"
    _description = "Cancel Multi Invoice"

    
    def action_cancel(self):
        invoices = self.env.context.get('active_ids')
        cancel_invoices = self.env['account.move'].browse(invoices)
        res = True
        for cancel_invoice in cancel_invoices:
            res = cancel_invoice.with_context(Flag=True).button_cancel()
        return res