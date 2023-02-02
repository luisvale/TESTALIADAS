# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError

SELECTION_ADD = [
    ('other', 'Otros')
]

class HrSalaryAttachmentDeduction(models.Model):
    _name = 'hr.salary.attachment.deduction'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Nómina: Tipo de deducción'

    sequence = fields.Integer(default=10)
    name = fields.Char(string='´Nombre')
    code = fields.Char(string='Código')
    company_id = fields.Many2one('res.company', string='Compañía', required=True, default=lambda self: self.env.company)
    active = fields.Boolean(string='Activo', default=True)

    input_type_id = fields.Many2one('hr.payslip.input.type', string='Otras entradas')

    _sql_constraints = [
        ('code_uniq', 'unique (code)', "El código del tipo de deducción ya existe!"),
    ]


class HrSalaryAttachment(models.Model):
    _inherit = 'hr.salary.attachment'

    deduction_id = fields.Many2one('hr.salary.attachment.deduction', string='Deduction')

    @api.model
    def _get_selection(self):
        deduction = self.env['hr.salary.attachment.deduction'].sudo().search([('active','=',True)])
        ded_list = []
        for d in deduction:
            ded_list.append((d.code, d.name))
        return ded_list

    deduction_type = fields.Selection(
        selection=_get_selection,
        string='Type',
        required=True,
        default='attachment',
        tracking=True,
    )

    @api.onchange('deduction_id')
    def _onchange_deduction_id(self):
        for record in self:
            if record.deduction_id and record.deduction_id.code not in ['attachment','assignment','child_support']:
                record.deduction_type = record.deduction_id.code
                #record.deduction_type = 'other'


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    @api.model
    def _get_attachment_types(self):

        types = {}

        deduction = self.env['hr.salary.attachment.deduction'].sudo().search([('active', '=', True),('company_id','=',self.env.company.id)])
        for d in deduction:
            types[d.code] = d.input_type_id

        return types

        #
        # return {
        #     'attachment': self.env.ref('hr_payroll.input_attachment_salary'),
        #     'assignment': self.env.ref('hr_payroll.input_assignment_salary'),
        #     'child_support': self.env.ref('hr_payroll.input_child_support'),
        # }