# -*- coding: utf-8 -*-

import ast

from datetime import date, datetime, timedelta

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT

class MaintenanceTeam(models.Model):
    _inherit = 'maintenance.team'

    periodic_ids = fields.One2many('maintenance.periodic', 'maintenance_team_id', copy=False)
    todo_periodic_ids = fields.One2many('maintenance.periodic', string="Requests", copy=False, compute='_compute_todo_periodic')
    todo_periodic_count = fields.Integer(string="Number of Requests", compute='_compute_todo_periodic')
    todo_periodic_count_date = fields.Integer(string="Number of Requests Scheduled", compute='_compute_todo_periodic')
    todo_periodic_count_high_priority = fields.Integer(string="Number of Requests in High Priority", compute='_compute_todo_periodic')
    todo_periodic_count_unscheduled = fields.Integer(string="Number of Requests Unscheduled", compute='_compute_todo_periodic')

    @api.depends('periodic_ids.state')
    def _compute_todo_periodic(self):
        for team in self:
            team.todo_periodic_ids = self.env['maintenance.periodic'].search([('maintenance_team_id', '=', team.id), ('state', '=', 'draft')])
            team.todo_periodic_count = len(team.todo_periodic_ids)
            team.todo_periodic_count_date = self.env['maintenance.periodic'].search_count([('maintenance_team_id', '=', team.id), ('date_start', '!=', False)])
            team.todo_periodic_count_high_priority = self.env['maintenance.periodic'].search_count([('maintenance_team_id', '=', team.id), ('priority', '=', '3')])
            team.todo_periodic_count_unscheduled = self.env['maintenance.periodic'].search_count([('maintenance_team_id', '=', team.id), ('date_start', '=', False)])
