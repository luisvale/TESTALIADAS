# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle 
#
##############################################################################

from odoo import models, fields, api, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    batch_credit_account_id = fields.Many2one('account.account', related='company_id.batch_credit_account_id', readonly=False, string="Credit Account")
    batch_debit_account_id = fields.Many2one('account.account', related='company_id.batch_debit_account_id', readonly=False, string="Debit Account")
    batch_salary_journal_id = fields.Many2one('account.journal', related='company_id.batch_salary_journal_id', readonly=False, string='Salary Journal')
    
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
