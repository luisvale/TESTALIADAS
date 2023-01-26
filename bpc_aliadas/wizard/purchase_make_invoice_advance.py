# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PurchaseAdvancePaymentInv(models.TransientModel):
    _name = "purchase.advance.payment.inv"
    _description = "Anticipo a facturas de compras"

    @api.model
    def _count(self):
        return len(self._context.get('active_ids', []))

    @api.model
    def _default_product_id(self):
        product_id = self.env['ir.config_parameter'].sudo().get_param('sale.default_deposit_product_id')
        return self.env['product.product'].browse(int(product_id)).exists()

    @api.model
    def _default_deposit_account_id(self):
        return self._default_product_id()._get_product_accounts()['expense']

    @api.model
    def _default_deposit_taxes_id(self):
        return self._default_product_id().taxes_id

    @api.model
    def _default_has_down_payment(self):
        if self._context.get('active_model') == 'purchase.order' and self._context.get('active_id', False):
            purchase_order = self.env['purchase.order'].browse(self._context.get('active_id'))
            return purchase_order.order_line.filtered(
                lambda purchase_order_line: purchase_order_line.is_downpayment
            )

        return False

    @api.model
    def _default_currency_id(self):
        if self._context.get('active_model') == 'purchase.order' and self._context.get('active_id', False):
            purchase_order = self.env['purchase.order'].browse(self._context.get('active_id'))
            return purchase_order.currency_id

    advance_payment_method = fields.Selection([
        ('delivered', 'Factura regular'),
        ('percentage', 'Pago inicial (porcentaje)'),
        ('fixed', 'Pago inicial (cantidad fija)')
        ], string='Crear factura', default='delivered', required=True,
        help="Se emite una factura estándar con todas las líneas de pedido listas para facturar, \
        de acuerdo con su política de facturación (basada en la cantidad ordenada o entregada)).")
    deduct_down_payments = fields.Boolean('Deducir pagos iniciales', default=True)
    has_down_payments = fields.Boolean('Tiene pagos inciales', default=_default_has_down_payment, readonly=True)
    product_id = fields.Many2one('product.product', string='Producto', domain=[('type', '=', 'service')],
        default=_default_product_id)
    count = fields.Integer(default=_count, string='# Órdenes')
    amount = fields.Float('Importe', digits='Account', help="El porcentaje del importe a facturar por adelantado, impuestos excluidos.")
    currency_id = fields.Many2one('res.currency', string='Moneda', default=_default_currency_id)
    fixed_amount = fields.Monetary('Importe del pago inicial (fijo)', help="El importe fijo a facturar por adelantado, impuestos excluidos.")
    deposit_account_id = fields.Many2one("account.account", string="Cuenta de ingreso", domain=[('deprecated', '=', False)],
        help="Cuenta utilizada para depósitos", default=_default_deposit_account_id)
    deposit_taxes_id = fields.Many2many("account.tax", string="Impuestos de clientes", help="Impuestos utilizados para los depósitos", default=_default_deposit_taxes_id)

    purchase_id = fields.Many2one('purchase.order', string='Orden compra', required=True, store=True, readonly=True)

    @api.onchange('advance_payment_method')
    def onchange_advance_payment_method(self):
        if self.advance_payment_method == 'percentage':
            amount = self.default_get(['amount']).get('amount')
            return {'value': {'amount': amount}}
        return {}

    def _prepare_invoice_values(self, order, name, amount, po_line):
        partner_invoice_id = order.partner_id.address_get(['invoice'])['invoice']
        partner_bank_id = order.partner_id.commercial_partner_id.bank_ids.filtered_domain(['|', ('company_id', '=', False), ('company_id', '=', order.company_id.id)])[:1]

        invoice_vals = {
            'ref': order.partner_ref,
            'move_type': 'in_invoice',
            'document_type_purchase_id': self.env.ref('hn_einvoice.document_factura_electronica').id,
            'narration': order.notes,
            'currency_id': order.currency_id.id,
            'invoice_user_id': order.user_id and order.user_id.id or self.env.user.id,
            'partner_id': partner_invoice_id,
            'fiscal_position_id': (order.fiscal_position_id or order.fiscal_position_id.get_fiscal_position(partner_invoice_id)).id,
            'payment_reference': order.partner_ref or '',
            'partner_bank_id': partner_bank_id.id,
            'invoice_origin': order.name,
            'invoice_payment_term_id': order.payment_term_id.id,
            'company_id': order.company_id.id,
            'invoice_line_ids': [(0, 0, {
                'name': name,
                'price_unit': amount,
                'quantity': 1.0,
                'product_id': self.product_id.id,
                'product_uom_id': po_line.product_uom.id,
                'tax_ids': [(6, 0, po_line.taxes_id.ids)],
                'analytic_tag_ids': [(6, 0, po_line.analytic_tag_ids.ids)],
                'analytic_account_id': po_line.account_analytic_id.id if not po_line.display_type and po_line.account_analytic_id.id else False,
                'purchase_line_id': po_line.id
            })],
        }

        return invoice_vals

    def _get_advance_details(self, order):
        context = {'lang': order.partner_id.lang}
        if self.advance_payment_method == 'percentage':
            if all(self.product_id.taxes_id.mapped('price_include')):
                amount = order.amount_total * self.amount / 100
            else:
                amount = order.amount_untaxed * self.amount / 100
            name = _("Down payment of %s%%") % (self.amount)
        else:
            amount = self.fixed_amount
            name = _('Down Payment')
        del context

        return amount, name

    def _create_invoice(self, order, po_line, amount):
        if (self.advance_payment_method == 'percentage' and self.amount <= 0.00) or (self.advance_payment_method == 'fixed' and self.fixed_amount <= 0.00):
            raise UserError(_('The value of the down payment amount must be positive.'))

        amount, name = self._get_advance_details(order)

        invoice_vals = self._prepare_invoice_values(order, name, amount, po_line)

        if order.fiscal_position_id:
            invoice_vals['fiscal_position_id'] = order.fiscal_position_id.id

        invoice = self.env['account.move'].with_company(order.company_id)\
            .sudo().create(invoice_vals).with_user(self.env.uid)
        invoice.message_post_with_view('mail.message_origin_link',
                    values={'self': invoice, 'origin': order},
                    subtype_id=self.env.ref('mail.mt_note').id)
        return invoice

    def _prepare_po_line(self, order, analytic_tag_ids, tax_ids, amount):
        context = {'lang': order.partner_id.lang}
        po_values = {
            'name': _('Down Payment: %s') % (time.strftime('%m %Y'),),
            'price_unit': amount,
            'product_qty': 0.0,
            'order_id': order.id,
            'product_uom': self.product_id.uom_id.id,
            'product_id': self.product_id.id,
            'analytic_tag_ids': analytic_tag_ids,
            'taxes_id': [(6, 0, tax_ids)],
            'is_downpayment': True,
            'sequence': order.order_line and order.order_line[-1].sequence + 1 or 10,
            #'document_type_purchase_id': self.env.ref('hn_einvoice.document_factura_electronica').id
        }
        del context
        return po_values

    def create_invoices(self):
        purchase_orders = self.env['purchase.order'].browse(self._context.get('active_ids', []))
        moves = self.env['account.move']
        if self.advance_payment_method == 'delivered':
            purchase_orders.action_create_invoice_delivered(final=self.deduct_down_payments)
        else:
            # Create deposit product if necessary
            if not self.product_id:
                vals = self._prepare_deposit_product()
                self.product_id = self.env['product.product'].sudo().create(vals)
                self.env['ir.config_parameter'].sudo().set_param('sale.default_deposit_product_id', self.product_id.id)

            purchase_line_obj = self.env['purchase.order.line']
            for order in purchase_orders:
                amount, name = self._get_advance_details(order)

                taxes = self.product_id.taxes_id.filtered(lambda r: not order.company_id or r.company_id == order.company_id)
                tax_ids = order.fiscal_position_id.map_tax(taxes).ids
                analytic_tag_ids = []
                for line in order.order_line:
                    analytic_tag_ids = [(4, analytic_tag.id, None) for analytic_tag in line.analytic_tag_ids]

                po_line_values = self._prepare_po_line(order, analytic_tag_ids, tax_ids, amount)
                po_line = purchase_line_obj.create(po_line_values)
                moves += self._create_invoice(order, po_line, amount)
                #return purchase_orders.action_view_invoice(move)

        if self._context.get('open_invoices', False) and purchase_orders:
            return purchase_orders.action_view_invoice(moves)

        return {'type': 'ir.actions.act_window_close'}

    def _prepare_deposit_product(self):
        return {
            'name': _('Down payment'),
            'type': 'service',
            'invoice_policy': 'order',
            'property_account_expense_id': self.deposit_account_id.id,
            'taxes_id': [(6, 0, self.deposit_taxes_id.ids)],
            'company_id': False,
        }

