# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    sequence_id = fields.Many2one('ir.sequence', string='Secuencia', help='Secuencia del diario')
    sequence_return_id = fields.Many2one('ir.sequence', string='Secuencia rect.', help='Secuencia rectificativa del diario')
    sucursal_id = fields.Many2one('company.sucursal', copy=False, string='Sucursal')
    terminal_id = fields.Many2one('company.terminal', copy=False)
    cai_ids = fields.Many2many('res.cai')
    sequence_without_id = fields.Many2one('ir.sequence', string='Secuencia sin CAI', help='Secuencia del diario si CAI')



    def generate_sequence(self):
        for record in self:
            env_sequence = self.env['ir.sequence'].sudo()
            code = 'account.journal.%s' % record.code

            sequence = env_sequence.search([('code', '=', code), ('company_id', '=', record.company_id.id)])
            if not sequence:
                sequence = self.env['ir.sequence'].create({
                    'name': 'Secuencia %s' % record.name,
                    'code': code,
                    'padding': 6,
                    'prefix': record.code + '/%(year)s/',
                    'number_next': 1,
                    'number_increment': 1,
                    'company_id': record.company_id.id,
                })

            if sequence:
                record.sequence_id = sequence
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'type': 'success',
                        'title': _('Bien!'),
                        'message': _("Secuencia generada correctamente."),
                        'next': {'type': 'ir.actions.act_window_close'},
                    }
                }

    def generate_sequence_rect(self):
        for record in self:
            env_sequence = self.env['ir.sequence'].sudo()
            code = 'return.account.journal.%s' % record.code

            sequence = env_sequence.search([('code', '=', code), ('company_id', '=', record.company_id.id)])
            if not sequence:
                sequence = env_sequence.create({
                    'name': 'Secuencia rectificativa %s' % record.name,
                    'code': code,
                    'padding': 6,
                    'prefix': 'R' + record.code + '/%(year)s/',
                    'number_next': 1,
                    'number_increment': 1,
                    'company_id': record.company_id.id,
                })

            if sequence:
                record.sequence_return_id = sequence
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'type': 'success',
                        'title': _('Bien!'),
                        'message': _("Secuencia generada correctamente."),
                        'next': {'type': 'ir.actions.act_window_close'},
                    }
                }

    def generate_sequence_without_cai(self):
        for record in self:
            env_sequence = self.env['ir.sequence'].sudo()
            code = 'without.cai.account.journal.%s' % record.code

            sequence = env_sequence.search([('code', '=', code), ('company_id', '=', record.company_id.id)])
            if not sequence:
                sequence = self.env['ir.sequence'].create({
                    'name': 'Secuencia %s' % record.name,
                    'code': code,
                    'padding': 6,
                    'prefix': 'SNCAI' + record.code + '/%(year)s/',
                    'number_next': 1,
                    'number_increment': 1,
                    'company_id': record.company_id.id,
                })

            if sequence:
                record.sequence_without_id = sequence
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'type': 'success',
                        'title': _('Bien!'),
                        'message': _("Secuencia generada correctamente."),
                        'next': {'type': 'ir.actions.act_window_close'},
                    }
                }