# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta
from dateutil.relativedelta import relativedelta

from odoo import api, exceptions, fields, models, _

class ResCompany(models.Model):
    _name = 'res.company'
    _inherit = 'res.company'

    check_pricelist = fields.Boolean()
    sale_margin = fields.Float()
    #recurring_invoice_day = fields.Date()
    invoice_subscription_group_by = fields.Boolean()
    purchase_requisition_group_by = fields.Boolean()

    invoice_data_left = fields.Text()
    invoice_data_footer = fields.Text()

    hr_employee_sequence_id = fields.Many2one('ir.sequence', string='Secuencia')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    check_pricelist = fields.Boolean(related='company_id.check_pricelist', readonly=False)
    sale_margin = fields.Float(related='company_id.sale_margin', readonly=False)
    #recurring_invoice_day = fields.Date(related='company_id.recurring_invoice_day', reaonly=False)
    invoice_subscription_group_by = fields.Boolean(related='company_id.invoice_subscription_group_by', readonly=False)
    purchase_requisition_group_by = fields.Boolean(related='company_id.purchase_requisition_group_by', readonly=False)

    invoice_data_left = fields.Text(related='company_id.invoice_data_left', readonly=False)
    invoice_data_footer = fields.Text(related='company_id.invoice_data_footer', readonly=False)

    hr_employee_sequence_id = fields.Many2one('ir.sequence', string='Secuencia', related='company_id.hr_employee_sequence_id', readonly=False)


    def generate_hr_employee_sequence_id(self):
        sequence_employee_id = self.env['ir.sequence'].create({
            'name': 'Secuencia para código de empleado',
            'code': 'sequence.code.employee',
            'padding': 5,
            'number_next': 1,
            'number_increment': 1,
            'company_id': self.env.company.id,
        })

        self.sudo().write({'hr_employee_sequence_id': sequence_employee_id.id})