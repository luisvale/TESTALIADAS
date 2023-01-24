# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, date

STATES = [('draft', 'Borrador'),
          ('pending', 'Espera de productos'),
          ('done', 'Procesando picking'),
          ('process', 'En Proceso'),
          ('finished', 'Terminado'),
          ('cancel', 'Cancelado'),
          ]

class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    level_id = fields.Many2one('maintenance.level', string='Nivel')
    hours_estimated = fields.Float(string='Horas estimadas')
    maintenance_team_id = fields.Many2one('maintenance.team', string='Equipo')
    maintenance_id = fields.Many2one('maintenance.periodic')
    maintenance_state = fields.Selection(STATES, compute='_compute_maintenance', store=True)
    maintenance_parent_id = fields.Many2one('maintenance.periodic', compute='_compute_maintenance', store=True)
    contract_id = fields.Many2one('hr.contract', string='Contrato')
    #has_contract = fields.Boolean(string='Contrato', compute='_compute_contract')

    # def _compute_contract(self):
    #     for record in self:
    #         has_contract = False
    #         if record.employee_id:
    #             contract = self.env['hr.contract'].sudo().search([('employee_id', '=', record.employee_id.id), ('state', '=', 'open')], limit=1)
    #             if contract:
    #                 has_contract = True
    #             else:
    #                 has_contract = False
    #         record.has_contract = has_contract

    @api.depends('maintenance_id', 'maintenance_id.state','maintenance_id.parent_id')
    def _compute_maintenance(self):
        for record in self:
            record.maintenance_state = record.maintenance_id.state if record.maintenance_id else 'draft'
            record.maintenance_parent_id = record.maintenance_id.parent_id if record.maintenance_id else False

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        for record in self:
            if record.maintenance_id:
                contract = self.env['hr.contract'].sudo().search([('employee_id', '=', record.employee_id.id), ('state', '=', 'open')], limit=1)
                if contract:
                    record.contract_id = contract
