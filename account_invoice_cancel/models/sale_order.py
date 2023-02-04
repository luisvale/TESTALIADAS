from odoo import api, fields, models,exceptions


class SaleOrder(models.Model):
    _inherit = "sale.order"

    cancel_paid_invoice = fields.Boolean(string='Cancel Paid Invoice?', compute='check_cancel_paid_invoice')

    @api.model
    def check_cancel_paid_invoice(self):
        for order in self:
            Flag = False
            if order.company_id.cancel_paid_invoice and order.invoice_count > 0:
                for invoice in self.invoice_ids:
                    if invoice.state != 'cancel':
                        Flag = True
                        break
            order.cancel_paid_invoice = Flag
                

    
    def cancel_invoice(self):
        if len(self.invoice_ids) == 1 :
            self.invoice_ids.with_context({'Flag':True}).button_cancel()
            return self.action_view_invoice_for_app()
        else:
            return self.action_cancel_selected_invoice()
        
    
    def action_view_invoice_for_app(self):
        action = self.env.ref('account.action_move_out_invoice_type').read()[0]
        invoice_records = self.mapped('invoice_ids')
        if invoice_records:
            action['views'] = [(self.env.ref('account.view_move_form').id, 'form')]
            action['res_id'] = invoice_records.id
        return action

    
    def action_cancel_selected_invoice(self):
        invoice_obj = self.env['account.move']
        invoices = []
        for invoice in self.invoice_ids:
            if invoice.state !='cancel':
                invoices.append(invoice.id)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'cancel.invoice.wizard',
            'view_mode':'form',
            'views': [(self.env.ref('account_invoice_cancel.invoice_cancel_form_cft').id, 'form')],
            'target': 'new',
            'context': {
                    'invoices':invoices,
            },
        }
