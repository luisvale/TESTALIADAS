# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright 2019 EquickERP
#
##############################################################################
{
    'name' : 'Employee Allowances & Deductions',
    'category': 'Human Resources',
    'version': '15.0.1.0',
    'author': 'Equick ERP',
    'description': """This module is used for manage the employee allowance and deduction.
        * Employee can also record their own allowance or deduction.
        * Auto calculate in employee payslip. So HR/Payroll managers do not have to enter manually on the payslip for the extra input to salary calculation.
        * Support With Multi Company.
    """,
    'summary': """manage your employee allowance and deductions in payslip allowance extra allowance overtime allowance night shift allowance late coming deduction weekend working payroll allowance and deductions extra deduction payslip other input type referral bonus""",
    'depends' : ['base', 'hr_payroll'],
    'price': 60,
    'currency': 'EUR',
    'license': 'OPL-1',
    'website': "",
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'views/alw_ded_config_view.xml',
        'views/hr_payslip_view.xml'
    ],
    'demo': [],
    'live_test_url': 'https://www.youtube.com/watch?v=js4CNrIiC70',
    'images': ['static/description/main_screenshot.png'],
    'installable': True,
    'auto_install': False,
    'application': False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: