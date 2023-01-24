# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, date


class HrDepartment(models.Model):
    _name = 'hr.department'
    _inherit = 'hr.department'

    #
    departament_ids = fields.Many2many('hr.department', 'related_department_many', 'dep_id', 'departament_id', string='Departamentos')
    authorization_line_ids = fields.Many2many('department.authorization.line', compute='_compute_authorization_line_ids')

    def _compute_authorization_line_ids(self):
        for record in self:
            authorization_line_ids = False
            if len(record.ids)>0:
                authorization_line_ids = self.env['department.authorization.line'].sudo().search([('department_id','in',record.ids),
                                                                                                  ('company_id','=',record.company_id.id)])
            record.authorization_line_ids = authorization_line_ids


# class DepartmentAuthorizationLine(models.Model):
#     _name = 'department.authorization.line'
#     _inherit = ['mail.thread', 'mail.activity.mixin']
#     _description = 'Auorizacion por departamento'
#
#     dep_id = fields.Many2one('hr.department')
#     company_id = fields.Many2one('res.company', related='dep_id.company_id')
#     user_id = fields.Many2one('res.users', string='Usuario', required=True)


class DepartmentAuthorizationLine(models.Model):
    _name = 'department.authorization.line'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Autorizacion por departamentos'
    #_rec_name = 'user_id'

    department_id = fields.Many2one('hr.department', string='Departamento',required=True)
    department_user_id = fields.Many2one('hr.department', compute='_compute_department_user_id', string='Dpto. usuario')
    company_id = fields.Many2one('res.company', required=True, related='department_id.company_id', string='Compañía')
    existing_user_ids = fields.Many2many('res.users', compute='_compute_existing_user_ids')
    user_id = fields.Many2one('res.users', string='Usuario', required=True)
    level_id = fields.Many2one('approval.level', string='Nivel', required=True)
    amount_lines = fields.One2many('authorization.interval.line', 'authorization_id', string='Montos')

    _sql_constraints = [
        ('name_department_uid_unique', 'unique (user_id, department_id)', 'No puede asignar el usuario más de una vez al mismo departamento.'),
    ]

    @api.depends('department_id')
    def _compute_existing_user_ids(self):
        for record in self:
            record.existing_user_ids = False
            #record.existing_user_ids = record.department_id.authorization_lines.user_id

    def name_get(self):
        res = []
        for record in self:
            name = '%s - %s ' % (record.user_id.name, record.department_id.name)
            res.append((record.id, name))
        return res

    @api.depends('user_id')
    def _compute_department_user_id(self):
        for record in self:
            department_id = False
            if record.user_id:
                employee_id = self.env['hr.employee'].sudo().search([('user_id', '=', record.user_id.id)], limit=1)
                if employee_id:
                    department_id = employee_id.department_id

            record.department_user_id = department_id

class AuthorizationIntervalLine(models.Model):
    _name = 'authorization.interval.line'
    _description = 'Aprobación con intervalos por departamentos'

    authorization_id = fields.Many2one('department.authorization.line')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Moneda', required=True, default=lambda x: x.env.company.currency_id)
    amount_from = fields.Monetary(string='Desde', default=0.0)
    amount_to = fields.Monetary(string='Hasta', default=0.0)

    def name_get(self):
        res = []
        for record in self:
            name = 'De %s %s a %s %s ' % (record.currency_id.symbol, record.amount_from, record.currency_id.symbol, record.amount_to)
            res.append((record.id, name))
        return res


