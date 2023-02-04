# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle 
#
##############################################################################
{
    'name': 'Batch Payslip Payment, Payslip Payment',
    'version': '15.0.1.0',
    'sequence': 1,
    'category': 'Human Resources',
    'description':
        """ 
  This Apps add below functionality into odoo 
        
        1.This module helps you to generate batch payslip payment
        
    """,
    'summary': 'odoo app Generate Batch Payslip Payment, payslip payment, payslip account payment, payslip payment employee', 
    'author': 'DevIntelle Consulting Service Pvt.Ltd', 
    'website': 'http://www.devintellecs.com',
    'depends': ['hr_payroll'],
    'data': [
        'security/ir.model.access.csv',
        'security/hr_payroll_security.xml',
        'data/sequence.xml',
        'data/email_template.xml',
        'views/res_config_views.xml',
        'views/dev_batch_payslip_payment_views.xml',
        'views/hr_payslip.xml',
    ],
    'demo': [],
    'test': [],
    'css': [],
    'qweb': [],
    'js': [],
    'images': ['images/main_screenshot.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
    
    # author and support Details =============#
    'author': 'DevIntelle Consulting Service Pvt.Ltd',
    'website': 'http://www.devintellecs.com',    
    'maintainer': 'DevIntelle Consulting Service Pvt.Ltd', 
    'support': 'devintelle@gmail.com',
    'price':10.0,
    'currency':'EUR',
    #'live_test_url':'https://youtu.be/A5kEBboAh_k',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
