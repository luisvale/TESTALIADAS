# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, date
import json
import logging
_logger = logging.getLogger(__name__)

TYPE = [('interest','Interés'),
        ('quote','Cotización'),
        ('quote_send','Cotización enviada'),
        ('negotiation','Negociación'),
        ('document_review','Revisión documentos'),
        ('contract','Contrato'),
        ('win','Ganado (Pagado)'),
        ('lost','Perdido'),
        ]

TRADUCTION = {
    'interest': 'Interés',
    'quote': 'Cotización',
    'quote_send': 'Cotización enviada',
    'negotiation': 'Negociación',
    'document_review': 'Revisión documentos',
    'contract': 'Contrato',
    'win': 'Ganado (Pagado)',
    'lost': 'Perdido',
}

STATE_PROSPECT = [('done', 'Confirmado'), ('draft', 'Prospecto'), ('cancel', 'Rechazado'), ('inactive','Inactivo')]


class CrmStage(models.Model):
    _inherit = 'crm.stage'

    type_stage = fields.Selection(TYPE, string='Tipo etapa', required=True, tracking=True)

    @api.onchange('type_stage')
    def _onchange_type_stage(self):
        for record in self:
            if record.type_stage:
                record.name = TRADUCTION[record.type_stage]


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    partner_prospect_id = fields.Many2one('res.partner', domain=[('active', '=', False), ('state', '=', 'draft')], string='Prospecto cliente')
    partner_prospect_state = fields.Selection(STATE_PROSPECT, compute='_compute_partner_prospect_state', string='Estado cliente')

    is_paid = fields.Boolean(string='Pagado')
    is_firm = fields.Boolean(string='Firmado')
    last_stage_id = fields.Many2one('crm.stage', string='Última etapa')
    states_list = fields.Text(string='Lista de estados')

    @api.depends('partner_prospect_id', 'partner_prospect_id.state', 'partner_prospect_id.active')
    def _compute_partner_prospect_state(self):
        for record in self:
            if record.partner_prospect_id:
                record.partner_prospect_state = record.partner_prospect_id.state
                record.partner_id = record.partner_prospect_id
            elif record.partner_id:
                record.partner_prospect_state = record.partner_id.state
            else:
                record.partner_prospect_state = 'done'

    @api.constrains('is_paid', 'is_firm')
    def _constraint_paid_firm(self):
        for lead in self:
            if lead.is_paid and lead.is_firm and not lead.stage_id.is_won:
                _logger.info("DEBE PASAR A GANADO")
                lead.lead_next_stage('win')
                lead.sudo().action_set_won_rainbowman()
            #elif lead.stage_id.is_lose:

    def lead_next_stage(self, new_state):
        for record in self:
            _logger.info("ALIADAS: Lead pasa de estado %s " % record.stage_id.name)
            stage_id = self.env['crm.stage'].sudo().search([('type_stage','=',new_state)])
            if stage_id:
                record.sudo().write({'stage_id': stage_id.id})
                _logger.info("ALIADAS: A este estado %s " % record.stage_id.name)

    # @api.depends('order_ids.state', 'order_ids.currency_id', 'order_ids.amount_untaxed', 'order_ids.date_order', 'order_ids.company_id','order_ids.accept_and_signed')
    # def _compute_sale_data(self):
    #     super(CrmLead, self)._compute_sale_data()
    #     for lead in self:
    #         #if lead.stage_id
    #         for order in lead.order_ids:
    #             if order.state == 'sent' and lead.stage_id.type_stage == 'quote':
    #                 _logger.info("DEBE PASAR A COTIZACIÓN ENVIADA")
    #                 lead.lead_next_stage('quote_send')
    #
    #             elif order.accept_and_signed and lead.stage_id.type_stage == 'quote_send':
    #                 _logger.info("DEBE PASAR A REV.CUMPLIMIENTO")
    #                 lead.lead_next_stage('contract')
    #
    #             elif order.state == 'sale' and lead.stage_id.type_stage == 'document_review':
    #                 _logger.info("DEBE PASAR A CONTRATO")
    #                 lead.lead_next_stage('contract')

    def action_set_lost(self, **additional_values):
        if type(additional_values) == dict:
            stage_lost = self.env['crm.stage'].sudo().search([('type_stage', '=', 'lost')], limit=1)
            if stage_lost:
                additional_values.update({
                    'last_stage_id': self.stage_id.id,
                    'stage_id': stage_lost.id
                })
        return super(CrmLead, self).action_set_lost(**additional_values)

    def toggle_active(self):
        res = super(CrmLead, self).toggle_active()
        if self.last_stage_id:
            self.sudo().write({'stage_id': self.last_stage_id.id})
        return res

    def action_new_quotation(self):
        action = super(CrmLead, self).action_new_quotation()
        action['context']['default_partner_prospect_id'] = self.partner_prospect_id.id

        return action

    def _get_action_rental_context(self):
        context = super(CrmLead, self)._get_action_rental_context()
        context['default_partner_prospect_id'] = self.partner_prospect_id.id
        return context
