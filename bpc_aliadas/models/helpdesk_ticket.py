# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, date
import logging
_logger = logging.getLogger(__name__)

_MAINTENANCE_TYPE = [('internal','Interno'), ('external','Externo')]

class HelpdeskStage(models.Model):
    _inherit = 'helpdesk.stage'

    send_mail = fields.Boolean(string='Enviar email automático', help='Al activar este campo cuándo el ticket pase a este estado tomará la plantilla de mail'
                                                                      ' y lo enviará directamente al cliente.')

class HelpdeskTeam(models.Model):
    _inherit = 'helpdesk.team'

    is_maintenance = fields.Boolean(string='Es mantenimiento')
    sale_team_id = fields.Many2one('crm.team', string='Equipo de ventas')
    maintenance_type = fields.Selection(_MAINTENANCE_TYPE, string='Tipo mant.', default='internal')

class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    is_maintenance = fields.Boolean(related='team_id.is_maintenance')
    sale_team_id = fields.Many2one('crm.team', related='team_id.sale_team_id')
    commercial_name = fields.Many2one('res.partner.commercial', string='Nombre comercial')
    contract = fields.Char(string='Contrato', index=True, website_form_blacklisted=False)
    subscription_id = fields.Many2one('sale.subscription', string='Subscripción', compute='_compute_subscription_id', store=True,
                                      readonly=False, domain="[('partner_id','=',partner_id)]")
    contract_name = fields.Char(string='Contrato', related='subscription_id.contract_name')

    local_ids = fields.Many2many('product.template', related='subscription_id.local_ids', string='Locales')
    square_id = fields.Many2one('account.analytic.account', string='Plaza')

    #send_mail = fields.Boolean(compute='_compute_send_mail', tracking=True, string='Mail enviado')

    @api.constrains('product_id','partner_id')
    def _constraint_product_and_partner(self):
        for record in self:
            record._find_locals_by_customer()

    def _find_locals_by_customer(self):
        self.ensure_one()
        if self.partner_id:
            _logger.info("Búsqueda de subscripción según cliente %s " % self.partner_id.name)
            subs = self.env['sale.subscription'].sudo().search([('partner_id', '=', self.partner_id.id)])
            if subs:
                _logger.info("Subscripción encontrada")
                local_ids = subs.local_ids
                if local_ids and self.product_id:
                    if self.product_id.product_tmpl_id.id not in local_ids.ids:
                        raise ValidationError(_("El producto %s no está dentro de los locales del cliente." % self.product_id.name))
            else:
                _logger.info("Subscripción no encontrada")

    def view_subscription_by_contract(self):
        self.ensure_one()
        if self.contract:
            subcription_id = self._find_subscription_by_contract()
            if subcription_id:
                return {
                    'name': _('Subscripción'),
                    'view_mode': 'form',
                    'res_model': 'sale.subscription',
                    'type': 'ir.actions.act_window',
                    'res_id': subcription_id.id
                }
            else:
                raise ValidationError(_("No se encontró subscripción para número de contrato %s " % self.contract))

    def _find_subscription_by_contract(self):
        _logger.info("Buscando subscripción según contrato %s " % self.contract)
        self.ensure_one()
        subs = self.env['sale.subscription'].sudo().search(['|', ('name', '=', self.contract), ('contract_name', '=', self.contract)])
        if subs:
            _logger.info("Subscripción encontrada : %s " % subs.name)
        else:
            _logger.info("Subscripción no encontrada")
        return subs

    @api.depends('contract')
    def _compute_subscription_id(self):
        for record in self:
            subscription_id = False
            square_id = False
            if record.contract:
                subscription_id = record._find_subscription_by_contract()
                if subscription_id and subscription_id.analytic_account_id:
                    square_id = subscription_id.analytic_account_id
                    if subscription_id.local_ids:
                        record.product_id = subscription_id.local_ids[0].product_variant_id
            record.subscription_id = subscription_id
            record.square_id = square_id
            if record.subscription_id:
                record._complete_data_partner()

    def _complete_data_partner(self):
        self.ensure_one()
        self.partner_id = self.subscription_id.partner_id
        if self.partner_id:
            self.partner_name = self.partner_id.name
            self.partner_phone = self.partner_id.phone
            self.partner_email = self.partner_id.email

    @api.onchange('local_ids')
    def _onchange_local_ids(self):
        if self.local_ids:
            return {'domain': {'product_id': [('product_tmpl_id', 'in', self.local_ids.ids)]}}
        else:
            return {'domain': {'product_id': [('active', '=', True)]}}

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        self._clean_data()
        if self.partner_id:
            return {'domain': {'product_id': [('active', '=', True)]}}


    def _clean_data(self):
        self.contract = False
        self.commercial_name = False
        self.local_ids = []
        self.product_id = False

    @api.onchange('commercial_name')
    def _onchange_commercial_name(self):
        if self.commercial_name:
            self.partner_id = self.commercial_name.partner_id


    @api.onchange('stage_id')
    def _onchange_stage_id(self):
        for record in self:
            if record.stage_id.send_mail and record.stage_id.template_id:
                _logger.info("Envío de email para estado : %s " % record.stage_id.name)
                template = self.env.ref('bpc_aliadas.mail_template_helpdesk_ticket_rejection', raise_if_not_found=False)
                try:
                    record.sudo().activity_schedule('bpc_aliadas.mail_activity_data_helpdesk_ticket_refused',
                                                    user_id=record.user_id.id,
                                                    note='Rechazo de ticket: %s' % record.name)
                    res = template.sudo().send_mail(record.id, notif_layout='mail.mail_notification_light', force_send=True, )
                    _logger.info("Resultado del envío: %s " % res)
                except Exception as e:
                    _logger.warning("Error de envío de correo en ticket: %s " % e)

