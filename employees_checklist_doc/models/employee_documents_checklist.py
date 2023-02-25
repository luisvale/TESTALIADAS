# -*- encoding: utf-8 -*-

from datetime import datetime, time

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class EmployeeDocumentsChecklist(models.Model):
    _name = "employee.documents.check_list"
    _description = 'Check list de documentos de empleados'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence desc'
    _rec_name = 'name'

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    sequence = fields.Integer(string='Secuencia', required=True)
    name = fields.Char(string='Nombre', required=True)
    description = fields.Text(string='Descripción')
    state_active = fields.Boolean(default=True, string='Activo')
    date_due = fields.Date(string='Fecha vencimiento')
    type = fields.Selection([('sale','Ventas'), ('purchase','Compras')], string='Usado para', default='sale')

class EmployeeDocumentsChecklistLines(models.Model):
    _name = "employee.documents.check_list.lines"
    _description = 'Check list documentos empleado'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    employee_id = fields.Many2one('hr.employee', string='Empleado')
    check_list_id = fields.Many2one('employee.documents.check_list', string='Paso')
    check_list_type = fields.Selection(related='check_list_id.type')
    check_list_id_sequence = fields.Integer(related='check_list_id.sequence')
    check = fields.Boolean(string='Check')
    description = fields.Char(string='Observación')
    date_due = fields.Date(string='Fecha vencimiento')
