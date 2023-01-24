# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


class PurchaseOrderApprovedWizard(models.TransientModel):
    _name = "purchase.order.approved.wizard"
    _description = 'Aprobación de órdenes de venta'

    order_id = fields.Many2one('purchase.order', string='Orden de compra', required=True)
    note = fields.Text(string='Motivo', required=True)

    def confirm_approved(self):
        order_id = self.order_id
        order_id.sudo().message_notify(
            subject='Motivo de aprobación:',
            subtype_xmlid="mail.mt_note",
            message_type='comment',
            body='<p>%s</p>' % self.note,
            partner_ids=self.env.user.partner_id.ids,
        )
        order_id.sudo().write({'approved': True})
        lines_check = order_id.order_line.filtered(lambda o: o.check_purchase) #Cantidad de líneas que tienen el check
        if order_id.purchase_o_ids and len(lines_check.ids) == len(order_id.order_line.ids):
            for o in order_id.purchase_o_ids:
                o.button_cancel()

        order_id.sudo()._compute_exist_budget()

        if order_id.exist_budget:
           order_id.sudo().button_evaluation_to_draft()
        else:
            pass
            #order_id.sudo()._create_request('purchase_budget')

        #order_id.sudo().button_confirm()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': _('Bien!'),
                'message': _("La orden ha sido confirmada correctamente."),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }







