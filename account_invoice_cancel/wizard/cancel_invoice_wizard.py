from odoo import api, exceptions, fields, models, _


class CancelInvoiceWizard(models.TransientModel):
    _name = "cancel.invoice.wizard"
    _description="Cancel Invoice"
        
    invoice_ids = fields.Many2many('account.move','account_inv_cancel_invoice_wizard','invoice_id','wizard_id', string='Invoice')

    def clear_all_invoice(self):
        self.invoice_ids = False
        return {"type": "ir.actions.do_nothing"}

    def cancel_selected_invoice_orders(self):

        if self.invoice_ids:
           self.invoice_ids.with_context({'Flag':True}).button_cancel()
           return self.action_view_invoice()
    
    def action_view_invoice(self):
        '''
        This function returns an action that display existing invoice orders
        of given sales order ids. It can either be a in a list or in a form
        view, if there is only one invoice order to show.
        '''
        invoices = self.mapped('invoice_ids')
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_out_invoice_type")
        if len(invoices) > 1:
            action['domain'] = [('id', 'in', invoices.ids)]
        elif len(invoices) == 1:
            form_view = [(self.env.ref('account.view_move_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = invoices.id
        else:
            action = {'type': 'ir.actions.act_window_close'}

        return action
        # action = self.env.ref('account.view_out_invoice_tree').read()[0]

        # invoices = self.mapped('invoice_ids')
        # if len(invoices) > 1:
        #     action['domain'] = [('id', 'in', invoices.ids)]
        # elif invoices:
        #     action['views'] = [(self.env.ref('account.invoice_form').id, 'form')]
        #     action['res_id'] = invoices.id
        # return action
