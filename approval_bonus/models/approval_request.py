# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.date_utils import start_of
from odoo.tools import html2plaintext


class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    salary_att_id = fields.Many2one("hr.salary.attachment")
    employee_id = fields.Many2one("hr.employee")
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id')
    deduction_type = fields.Selection(
        selection=[
            ('attachment', 'Attachment of Salary'),
            ('assignment', 'Assignment of Salary'),
            ('child_support', 'Child Support'),
        ],
        string='Type',
        required=True,
        default='attachment',
        tracking=True,
    )
    monthly_amount = fields.Monetary(
        'Monthly Amount', required=True, tracking=True,
        help='Amount to pay each month.')
    total_amount = fields.Monetary(
        'Total Amount',
        tracking=True,
        help='Total amount to be paid.',
    )
    date_start = fields.Date(
        'Start Date', required=True,
        default=lambda r: start_of(fields.Date.today(), 'month'),
        tracking=True)

    def action_create_salary_attachment(self):
        self.ensure_one()
        if not self.employee_id:
            raise UserError("No se ha asignado el empleado!")
        if self.salary_att_id:
            raise UserError("Ya existe un adjunto del salario")
        salary_att_id = self.env["hr.salary.attachment"].create(
            {
                "employee_id": self.employee_id.id,
                "deduction_type": self.deduction_type,
                "monthly_amount": self.monthly_amount,
                "total_amount": self.total_amount,
                "date_start": self.date_start,
                "description": html2plaintext(self.reason) or ''
            }
        )
        self.salary_att_id = salary_att_id.id
