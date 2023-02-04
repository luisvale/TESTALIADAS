# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright 2019 EquickERP
#
##############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class hr_alw_ded(models.Model):
    _name = 'hr.alw.ded'
    _description = "Allowance and Deduction"
    _inherit = ['mail.thread']
    _order = 'ad_date desc, id desc'

    payslip_id = fields.Many2one('hr.payslip', string="Payslip", copy=False)
    name = fields.Char(string="Name", copy=False, index=True, default=lambda self: _('New'))
    ad_date = fields.Date(string="Date", default=fields.Date.today(), copy=False)
    ad_type = fields.Selection([('allowance', 'Allowance'),
                                ('deduction', 'Deduction')], string="Type", required=1, tracking=3)
    employee_id = fields.Many2one('hr.employee', string="Employee", required=1, tracking=3, default=lambda self: self.env.user.employee_id.id)
    hr_payslip_input_type_id = fields.Many2one('hr.payslip.input.type', string="Input Type", required=1, tracking=3)
    amount = fields.Float(string='Amount', required=1, tracking=3)
    note = fields.Text(string="Description", copy=False)
    state = fields.Selection([('draft', 'Draft'),
                              ('confirm', 'Confirm'),
                              ('approve', 'Approved'),
                              ('done', 'Done'),
                              ('reject', 'Rejected'),
                              ('cancel', 'Cancelled')], string="Status", default='draft', copy=False, tracking=3)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('alw.ded') or _('New')
        return super(hr_alw_ded, self).create(vals)

    def btn_confirm(self):
        self.write({'state': 'confirm'})

    def btn_approve(self):
        self.write({'state': 'approve'})

    def btn_reject(self):
        self.write({'state': 'reject'})

    def unlink(self):
        for had in self:
            if had.state != 'draft':
                raise ValidationError(_("You cannot delete the record as it is not in Draft state."))
        return super(hr_alw_ded, self).unlink()

    def btn_cancel(self):
        if self.payslip_id:
            raise ValidationError(_("You cannot cancel as it's already link with the payslip."))
        self.write({'state': 'cancel'})

    def btn_draft(self):
        self.write({'state': 'draft'})

    def mark_as_done(self):
        self.write({'state': 'done'})

    @api.constrains('amount')
    def check_amount_value(self):
        for had in self:
            if had.amount <= 0:
                raise ValidationError(_("Amount should be greater than 0."))

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: