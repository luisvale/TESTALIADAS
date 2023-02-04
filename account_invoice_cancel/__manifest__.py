# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name' : 'Cancel Invoice/Bill',
    'version' : '14.0',
    'author':'Craftsync Technologies',
    'category': 'account',
    'maintainer': 'Craftsync Technologies',    
    'description' : """invoice order cancel 
			cancel invoice
			invoice cancel 
			reverse invoice 
			invoice order cancel
			Stock cancel reverse accounting 
			Picking Cancel 
			Cancel Order 
			Cancel Picking 
			Cancel Invoice 
			Invoice Cancel 
			Cancel Receipts 
			Receipt Cancel 
			Cancel Order 
			Cancel shipment
			reverse invoice
			account invoice cancel in odoo 

			shipment cancel 
			account invoice cancel 
			Cancel Invoice Order 
			Cancel Outgoing invoice 
			Cancel Incoming Picking 
			Reset Stock Move/Picking

			Cancel move 
			reset move 
			return move 
			Reset Invoice Order 
			reverse Invoice Order 
			Return Invoice Order 
			return invoice 
			return invoice 
			reverse move 
			account cancel 
			return account 
			account return 
			Stock Picking Cancel 
			Stock Picking cancel and Reverse 
			cancel accounting entries 
			reverse account 
			account reverse 
			reverse account entries 
			account entry reverse 
			return account entry 
			account entry return
 """,
    'summary': """Enable auto cancel paid invoice or cancel invoice. Auto Cancel Paid Invoice and Auto Cancel Paid Bill From Sale and Purchase Orders.""",
    'website': 'https://www.craftsync.com/',
    'description' : """invoice order cancel 
			cancel invoice
			invoice cancel 
			reverse invoice 
			invoice order cancel
			Stock cancel reverse accounting 
			Picking Cancel 
			Cancel Order 
			Cancel Picking 
			Cancel Invoice 
			Invoice Cancel 
			Cancel Receipts 
			Receipt Cancel 
			Cancel Order 
			Cancel shipment
			reverse invoice
			account invoice cancel in odoo 

			shipment cancel 
			account invoice cancel 
			Cancel Invoice Order 
			Cancel Outgoing invoice 
			Cancel Incoming Picking 
			Reset Stock Move/Picking

			Cancel move 
			reset move 
			return move 
			Reset Invoice Order 
			reverse Invoice Order 
			Return Invoice Order 
			return invoice 
			return invoice 
			reverse move 
			account cancel 
			return account 
			account return 
			Stock Picking Cancel 
			Stock Picking cancel and Reverse 
			cancel accounting entries 
			reverse account 
			account reverse 
			reverse account entries 
			account entry reverse 
			return account entry 
			account entry return
 """,
    'license': 'OPL-1',
    'support':'info@craftsync.com',
    'depends' : ['sale_management'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/view_sale_order.xml',
        'views/invoice.xml',
        # 'views/view_purchase_order.xml',
        'wizard/view_cancel_invoice_wizard.xml',

    ],
    
    'installable': True,
    'application': True,
    'auto_install': False,
    'images': ['static/description/main_screen.png'],
    'price': 4.99,
    'currency': 'EUR',

}
