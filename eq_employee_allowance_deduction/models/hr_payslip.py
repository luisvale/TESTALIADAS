# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright 2019 EquickERP
#
##############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class hr_payslip(models.Model):
    _inherit = 'hr.payslip'

    @api.depends('alw_ded_ids', 'alw_ded_ids.payslip_id')
    def get_count_allow_deduct(self):
        for payslip in self:
            payslip.alw_ded_count = len(payslip.mapped('alw_ded_ids'))

    alw_ded_ids = fields.One2many('hr.alw.ded', 'payslip_id', string="Allowances & Deductions")
    alw_ded_count = fields.Integer(string="Number of Allowances & Deductions", compute="get_count_allow_deduct")

    @api.model
    def create(self, vals):
        res = super(hr_payslip, self).create(vals)
        if res:
            alw_ded_ids = self.env['hr.alw.ded'].search([('employee_id', 'in', res.employee_id.ids),
                                                         ('state', '=', 'approve'),
                                                         ('payslip_id', '=', False)])
            res.alw_ded_ids = [(5, 0, 0)] + [(4, had.id) for had in alw_ded_ids]
        return res

    def write(self, vals):
        res = super(hr_payslip, self).write(vals)
        if 'alw_ded_ids' in vals:
            self.get_employee_allowance_deduction()
        if 'input_line_ids' in vals:
            self.set_alw_ded_payslip_link()
        return res

    def get_employee_allowance_deduction(self):
        for payslip in self:
            ad_total = sum(payslip.alw_ded_ids.mapped('amount'))
            if ad_total == 0:
                continue
            ad_input_type_ids = payslip.alw_ded_ids.mapped('hr_payslip_input_type_id').ids
            lines_to_remove = payslip.input_line_ids.filtered(lambda x: x.input_type_id.id in ad_input_type_ids)
            input_lines_vals = [(2, line.id, False) for line in lines_to_remove]
            for had in payslip.alw_ded_ids:
                input_lines_vals.append((0, 0, {
                    'amount': had.amount,
                    'name': had.note,
                    'input_type_id': had.hr_payslip_input_type_id.id
                }))
            payslip.update({'input_line_ids': input_lines_vals})

    def set_alw_ded_payslip_link(self):
        for payslip in self:
            ad_input_type_ids = payslip.alw_ded_ids.mapped('hr_payslip_input_type_id').ids
            if payslip.input_line_ids.filtered(lambda line: line.input_type_id.id not in ad_input_type_ids):
                payslip.alw_ded_ids.write({'payslip_id': False})

    def view_payslip_allowance_deduction(self):
        return {'name': _("Allowances & Deductions"),
                'type': 'ir.actions.act_window', 
                'res_model': 'hr.alw.ded',
                'view_mode': 'tree,form',
                'domain': [('payslip_id', '=', self.id)]}

    def action_payslip_done(self):
        res = super(hr_payslip, self).action_payslip_done()
        for payslip in self:
            for had in payslip.alw_ded_ids:
                had.mark_as_done()
        return res

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: