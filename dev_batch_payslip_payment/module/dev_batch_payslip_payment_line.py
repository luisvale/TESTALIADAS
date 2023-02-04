# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle 
#
##############################################################################

from odoo import fields, models, api, _


class dev_batch_payslip_payment_line(models.Model):
    _name = 'dev.payslip.lines'

    payslip_id = fields.Many2one('hr.payslip', string='Payslip', copy=False)
    name = fields.Char('Name', related="payslip_id.number")  #
    employee_id = fields.Many2one('hr.employee', string="Emp Name", related='payslip_id.employee_id')  #
    salary = fields.Float('Net Salary', compute='get_net_salary')
    acc_num_id = fields.Many2one('res.partner.bank', string='Account No', related="employee_id.bank_account_id")
    bank_id = fields.Many2one('res.bank', string='Bank', related="acc_num_id.bank_id")  #
    swift_code = fields.Char('Swift Code', related="bank_id.bic")  #
    batch_payment_id = fields.Many2one('dev.batch.payslip.payment', string='Batch Payment', ondelete='cascade')

    @api.depends('payslip_id')
    def get_net_salary(self):
        for line in self:
            if line.payslip_id:
                line.salary = 0
                for com_line in line.payslip_id.line_ids:
                    if com_line.code == 'NET':
                        line.salary = com_line.total

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
