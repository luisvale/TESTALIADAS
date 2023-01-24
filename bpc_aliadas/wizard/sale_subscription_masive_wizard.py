# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class SaleSubscriptionAllWizard(models.TransientModel):
    _name = 'sale.subscription.all.wizard'
    _description = 'Aliadas: Ventas adicionales en subscripción'

    # def _default_subscription(self):
    #     return self.env['sale.subscription'].browse(self._context.get('active_ids'))
    #
    # subscription_ids = fields.Many2many('sale.subscription', string="Subscription", required=True, default=_default_subscription, ondelete="cascade")
    subscription_ids = fields.Many2many('sale.subscription', string="Subscripciones", required=True,ondelete="cascade")
    option_lines = fields.One2many('sale.subscription.all.wizard.option', 'wizard_id', string="Options")
    date_from = fields.Date("Fecha def inicio", default=fields.Date.today,
                            help="The discount applied when creating a sales order will be computed as the ratio between "
                                 "the full invoicing period of the subscription and the period between this date and the "
                                 "next invoicing date.")

    def create_sale_order(self):
        orders = self.env['sale.order'].sudo()
        for subscription in self.subscription_ids:
            self = self.with_company(subscription.company_id)
            fpos = self.env['account.fiscal.position'].get_fiscal_position(subscription.partner_id.id)
            sale_order_obj = self.env['sale.order']
            team = self.env['crm.team']._get_default_team_id(user_id=subscription.user_id.id)
            new_order_vals = {
                'partner_id': subscription.partner_id.id,
                'analytic_account_id': subscription.analytic_account_id.id,
                'team_id': team and team.id,
                'pricelist_id': subscription.pricelist_id.id,
                'payment_term_id': subscription.payment_term_id.id,
                'fiscal_position_id': fpos.id,
                'subscription_management': 'upsell',
                'origin': subscription.code,
                'company_id': subscription.company_id.id,
            }
            # we don't override the default if no payment terms has been set on the customer
            if subscription.partner_id.property_payment_term_id:
                new_order_vals['payment_term_id'] = subscription.partner_id.property_payment_term_id.id
            order = sale_order_obj.sudo().create(new_order_vals)
            order.message_post(body=(_("This upsell order has been created from the subscription ") + " <a href=# data-oe-model=sale.subscription data-oe-id=%d>%s</a>" % (subscription.id, subscription.display_name)))
            for line in self.option_lines:
                subscription.partial_invoice_line_all(order, line, date_from=self.date_from)
            order.order_line._compute_tax_id()
            orders += order

        if orders:
            return {
                "type": "ir.actions.act_window",
                "res_model": "sale.order",
                "views": [[False, "tree"], [False, "form"]],
                "name": "Órdenes de venta",
                "domain": [["id", "in", orders.ids]],
            }


class SaleSubscriptionAllWizardOption(models.TransientModel):
    _name = "sale.subscription.all.wizard.option"
    _description = 'Subscription Upsell Lines Wizard'

    name = fields.Char(string="Descripción")
    wizard_id = fields.Many2one('sale.subscription.all.wizard', required=True, ondelete="cascade")
    product_id = fields.Many2one('product.product', required=True, domain="[('recurring_invoice', '=', True)]", ondelete="cascade", string='Producto')
    uom_id = fields.Many2one('uom.uom', string="Unid. Medida", required=True, ondelete="cascade", domain="[('category_id', '=', product_uom_category_id)]")
    product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id', readonly=True)
    quantity = fields.Float(default=1.0, string='Cantidad')
    price_unit = fields.Float(string='Precio unit.')
    discount = fields.Float(string='Descuento')
    pickup_date = fields.Datetime(string="Desde")
    return_date = fields.Datetime(string="Hasta")
    is_local = fields.Boolean(compute='_compute_is_local', string='Es local')

    @api.onchange("product_id")
    def onchange_product_id(self):
        if not self.product_id:
            return
        else:
            self.name = self.product_id.get_product_multiline_description_sale()

            if not self.uom_id or self.product_id.uom_id.category_id.id != self.uom_id.category_id.id:
                self.uom_id = self.product_id.uom_id.id


    @api.depends('product_id')
    def _compute_is_local(self):
        for record in self:
            is_local = False
            product_rental_id = self.env.ref('bpc_aliadas.rental_product_bpc')
            if record.product_id.rent_ok and record.product_id.id != product_rental_id.id:
                is_local = True

            record.is_local = is_local
