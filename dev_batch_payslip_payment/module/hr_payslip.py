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

class hr_payslip(models.Model):
    _inherit='hr.payslip'
    
    batch_payment_id = fields.Many2one('dev.batch.payslip.payment',string="Payment")
    journal_id = fields.Many2one('account.journal', 'Salary Journal', readonly=True, required=False,
        states={'draft': [('readonly', False)]}, default=lambda self: self.env['account.journal'].search([('type', '=', 'general')], limit=1))
    
    
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:



