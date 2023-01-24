# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime, time

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class SubscriptionLineHistory(models.Model):
    _name = "subscription.line.history"
    _description = 'Aliadas : Historial de líneas de susbcripción'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence desc'
    _rec_name = 'name'

    move_line_id = fields.Many2one('account.move.line', string='Línea comprobante')
    move_id = fields.Many2one('account.move', string='Comprobante', related='move_line_id.move_id')
    subs_line_id = fields.Many2many('sale.subscription.line', string='Línea subscripción')
    subscription_id = fields.Many2one('sale.subscription', string='Subscripción')
    product_id = fields.Many2many('product.product', string='Product', related='move_line_id.product_id')
    currency_id = fields.Many2one('res.currency', string='Moneda')
    amount_invoiced = fields.Monetary(string='Monto facturado')
    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=True, default=lambda self: self.env.company)
    company_currency_id = fields.Many2one(string='Company Currency', readonly=True, related='company_id.currency_id')
    amount_company = fields.Monetary(string='Moneda compañía')
    date_start = fields.Date(string='Inicio')
    date_end = fields.Date(string='Fin')
    name = fields.Char(compute='_compute_name')
    active = fields.Boolean(default=True)

    @api.depends('move_id', 'subscription_id', 'product_id')
    def _compute_name(self):
        for record in self:
            name = ''
            if record.product_id:
                name += ('%s' % record.product_id.name)
            if record.subscription_id:
                name += ('/ %s' % record.subscription_id.name)
            if record.move_id:
                name += ('/ %s' % record.move_id.name)
            record.name = name
