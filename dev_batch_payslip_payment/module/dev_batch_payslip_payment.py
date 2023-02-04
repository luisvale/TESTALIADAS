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
from datetime import datetime
import calendar
from odoo.exceptions import ValidationError
from io import BytesIO
import xlwt
from xlwt import easyxf
import base64


class dev_batch_payslip_payment(models.Model):
    _name = 'dev.batch.payslip.payment'

    def get_start_date(self):
        month = datetime.now().month
        if month < 10:
            month = '0'+str(month)
        year = datetime.now().year
        return str(year) + '-' + str(month) + '-' + '01'

    def get_end_date(self):
        month = datetime.now().month
        year = datetime.now().year
        date_range = calendar.monthrange(year, month)
        if month < 10:
            month = '0'+str(month)
        return str(year) + '-' + str(month) + '-' + str(date_range[1])

    def _get_credit_account(self):
        company_id = self.env.user.company_id
        if company_id.batch_credit_account_id:
            return company_id.batch_credit_account_id.id

    def _get_debit_account(self):
        company_id = self.env.user.company_id
        if company_id.batch_debit_account_id:
            return company_id.batch_debit_account_id.id

    def _get_salary_journal(self):
        company_id = self.env.user.company_id
        if company_id.batch_salary_journal_id:
            return company_id.batch_salary_journal_id.id

    name = fields.Char("Name", copy=False, default='/', required=True)
    start_date = fields.Date('Start Date', required="1", default=get_start_date)
    end_date = fields.Date('End Date', required="1", default=get_end_date)
    payment_date = fields.Date('Payment Date', copy=False)
    bank_number = fields.Many2one('res.partner.bank', string='Bank Number', required=True)
    company_bank = fields.Many2one('res.bank', string='Company Bank')
    user_id = fields.Many2one('res.users', string='User', index=True, default=lambda self: self.env.user)
    payslip_line_ids = fields.One2many('dev.payslip.lines', 'batch_payment_id', string='Payslip Lines')
    total_amount = fields.Float('Payable Amount', compute='get_total_amount')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self:self.env.user.company_id)
    credit_account_id = fields.Many2one('account.account', string='Credit Account', default=_get_credit_account)
    debit_account_id = fields.Many2one('account.account', string='Debit Account', default=_get_debit_account)
    salary_journal_id = fields.Many2one('account.journal', string='Salary Journal', default=_get_salary_journal)
    move_id = fields.Many2one('account.move', string='Accounting Entry')
    excel_file = fields.Binary('Excel File')

    @api.depends('payslip_line_ids')
    def get_total_amount(self):
        for payment in self:
            amount = 0
            for line in payment.payslip_line_ids:
                amount += line.salary
            payment.total_amount = amount
                

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirm', 'Confirm'),
        ('paid', 'Paid'),
        ('cancel', 'Cancel'),
    ], 'Status', default='draft', copy=False)

    @api.model
    def create(self,vals):
        vals.update({
                    'name':self.env['ir.sequence'].next_by_code('dev.batch.payslip.payment') or '/'
                })
        return super(dev_batch_payslip_payment,self).create(vals)


    def copy(self, default=None):
        if default is None:
            default = {}
        default['name'] = '/'
        return super(dev_batch_payslip_payment, self).copy(default=default)

    def unlink(self):
        for payment in self:
            if payment.state != 'draft':
                raise ValidationError('Batch payment delete only in draft state!!!.')

    @api.onchange('bank_number')
    def onchage_bank_number(self):
        if self.bank_number:
            self.company_bank = self.bank_number.bank_id and self.bank_number.bank_id.id or ''

    def load_payslip(self):
        if self.payslip_line_ids:
            self.payslip_line_ids.unlink()
        payslip_pool = self.env['hr.payslip']
        payslip_ids = payslip_pool.search(
            [('date_from', '>=', self.start_date), ('date_to', '<=', self.end_date), ('state', 'in',['draft','verify'] ), ('company_id','=',self.company_id.id)])
        if payslip_ids:
            vals = []
            for payslip in payslip_ids:
                vals.append((0, 0, {
                    'payslip_id': payslip.id,
                }))
            self.payslip_line_ids = vals

    def make_url(self, model='dev.batch.payslip.payment'):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', default='http://localhost:8069')
        if base_url:
            base_url += '/web/login?db=%s&login=%s&key=%s#id=%s&model=%s' % (self._cr.dbname, '', '', self.id, model)
        return base_url

    def send_mail(self):  
        template_id = self.env['ir.model.data']._xmlid_lookup('dev_batch_payslip_payment.email_batch_payslip_confirm')[2]
        mtp = self.env['mail.template'].browse(template_id)
        group_id = self.env['ir.model.data']._xmlid_lookup('account.group_account_manager')[2]
        group_id = self.env['res.groups'].browse(group_id)
        employee_lst = []
        emp_pool = self.env['hr.employee']
        mail_mail = self.env['mail.mail']
        for user in group_id.users:
            employee_ids = emp_pool.search([('user_id', '=', user.id)])
            for emp in employee_ids:
                if emp.company_id.id == self.company_id.id:
                    employee_lst.append(emp)
        subject = 'Batch Payslip Payment ' + self.name + ' waiting for your action'
        for employee in employee_lst:
            if employee.work_email:
                mtp.email_to = employee.work_email
                mtp.send_mail(self.id,force_send=True)

    def action_confirm(self):
        if not self.payslip_line_ids:
            raise ValidationError('No any Payslip Loaded !')
        self.send_mail()
        for line in self.payslip_line_ids:
            line.payslip_id.compute_sheet()
            
        self.state = 'confirm'

    def create_account_move(self):
        move_pool = self.env['account.move']
        vals = {
            'date': self.payment_date,
            'journal_id': self.salary_journal_id and self.salary_journal_id.id or False,
            'ref': self.name,
        }
        move_id = move_pool.create(vals)
        vals = []
        vals.append((0, 0, {
            'account_id': self.credit_account_id and self.credit_account_id.id or False,
            'credit': self.total_amount or 0.0,
            'debit': 0.0,
            'name': 'Salary Paid'
        }))

        vals.append((0, 0, {
            'account_id': self.debit_account_id and self.debit_account_id.id or False,
            'debit': self.total_amount or 0.0,
            'credit': 0.0,
            'name': 'Salary Paid'
        }))
        move_id.line_ids = vals
        move_id.post()
        self.move_id = move_id and move_id.id or False

    def action_paid(self):
        self.payment_date = datetime.today().date()
        self.create_account_move()
        self.state = 'paid'
        for line in self.payslip_line_ids:
            line.payslip_id.state = 'done'
            line.payslip_id.batch_payment_id = self.id

    def action_cancel(self):
        self.state = 'cancel'

    def action_draft(self):
        self.state = 'draft'
    
    def export_excel(self):
        workbook = xlwt.Workbook()
        filename = 'Batch Payslip Payment.xls'    
        worksheet = workbook.add_sheet('Batch Payslip Payment')
        main_header_style = easyxf('font:height 400;pattern: pattern solid, fore_color gray25;'
                                   'align: horiz center;font: color black; font:bold True;'
                                   "borders: top thin,left thin,right thin,bottom thin")
                                   
        header_style = easyxf('font:height 200;pattern: pattern solid, fore_color gray25;'
                              'align: horiz center;font: color black; font:bold True;'
                              "borders: top thin,left thin,right thin,bottom thin")
        
        text_left = easyxf('font:height 150; align: horiz left;' "borders: top thin,bottom thin")                    
        text_center = easyxf('font:height 150; align: horiz center;' "borders: top thin,bottom thin")
        text_right = easyxf('font:height 150; align: horiz right;' "borders: top thin,bottom thin",
                            num_format_str='0.00')      
                                          
        
        text_right_bold = easyxf('font:height 200; align: horiz right;font:bold True;' "borders: top thin,bottom thin", num_format_str='0.00')
                              
        worksheet.write_merge(0, 1, 0, 5, 'Batch Payslip Payment', main_header_style)
        
        for i in range(0, 9):
                worksheet.col(i).width = 150 * 30
                
        
        worksheet.write(4, 0, 'Account no', header_style)
        worksheet.write(4, 1, 'Bank Name', header_style)
        worksheet.write(4, 2, 'Swift Code', header_style)
        worksheet.write(4, 3, 'Start Date', header_style)
        worksheet.write(4, 4, 'End Date', header_style)
        
        start_date =False
        if self.start_date:
            start_date = self.start_date.strftime('%d-%m-%Y')
            
        end_date =False
        if self.end_date:
            end_date = self.end_date.strftime('%d-%m-%Y')
        
        worksheet.write(5, 0, self.bank_number.acc_number or '', text_center)
        worksheet.write(5, 1, self.company_bank.name or '', text_center)
        worksheet.write(5, 2, self.company_bank.bic or '', text_center)
        worksheet.write(5, 3, start_date or '', text_center)
        worksheet.write(5, 4, end_date or '', text_center)
        
        
        
        worksheet.write(8, 0, 'Payslip', header_style)
        worksheet.write(8, 1, 'Emp Name', header_style)
        worksheet.write(8, 2, 'A/C No', header_style)
        worksheet.write(8, 3, 'Bank', header_style)
        worksheet.write(8, 4, 'Swift Code', header_style)
        worksheet.write(8, 5, 'Net Salary', header_style)   
        
        r=9
        for line in self.payslip_line_ids:
            worksheet.write(r, 0, line.name, text_left)
            worksheet.write(r, 1, line.employee_id.name or '', text_left)
            worksheet.write(r, 2, line.acc_num_id.acc_number or '', text_center)
            worksheet.write(r, 3, line.bank_id.name or '', text_center)
            worksheet.write(r, 4, line.swift_code or '', text_center)
            worksheet.write(r, 5, line.salary, text_right)
            r+=1
             
        worksheet.write(r, 4, 'Total Payment', header_style) 
        worksheet.write(r, 5, self.total_amount, text_right_bold) 
        
        
        
        
        fp = BytesIO()
        workbook.save(fp)
        fp.seek(0)
        excel_file = base64.encodestring(fp.read())
        fp.close()
        self.write({'excel_file': excel_file})

        if self.excel_file:
            return {
                'type': 'ir.actions.act_url',
                'url': 'web/content/?model=dev.batch.payslip.payment&download=true&field=excel_file&id=%s&filename=%s' % (
                    self.id, filename),
                'target': 'new',
            }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
