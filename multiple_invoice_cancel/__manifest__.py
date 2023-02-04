# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name' : 'Cancel Multiple Invoices/Bills',
    'version' : '1.0',
    'author':'Craftsync Technologies',
    'category': 'account',
    'maintainer': 'Craftsync Technologies',
    'summary': "Enable mass cancel invoice order workflow. Even if invoice was transfered.Now user can select multi invoice order for cancel",
    'website': 'https://www.craftsync.com/',
    'license': 'OPL-1',
    'support':'info@craftsync.com',
    'depends' : ['account_invoice_cancel'],
    'data': [
       'security/ir.model.access.csv',
	   'views/view_cancel_multi_invoice.xml',
    ],    
    'installable': True,
    'application': True,
    'auto_install': False,
    'images': ['static/description/main_screen.png'],
    'price': 5.00,
    'currency': 'USD',

}
