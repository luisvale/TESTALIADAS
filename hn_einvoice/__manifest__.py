# -*- coding: utf-8 -*-
{
    'name': "hn_einvoice",

    'summary': """
        Facturación Honduras""",
    'description': """
        Módulo personalizado para compañía de Honduras
    """,
    'author': "Jhonny Mack Meriino Samillán",
    'company': 'BPC LATAM',
    'website': "https://www.bpc-lat.com/",
    'category': 'Sales',
    'version': '15.0.5.6',
    # any module necessary for this one to work correctly
    'depends': ['base', 'sale', 'account'],
    # always loaded
    'data': [
        #security
        'security/ir.model.access.csv',
        #data
        'data/document_type_data.xml',
        'data/sequence.xml',
        #views
        'views/document_type_views.xml',
        'views/company_sucursal_views.xml',
        'views/company_terminal_views.xml',
        'views/res_cai_customers_views.xml',
        'views/res_cai_suppliers_views.xml',
        'views/res_cai_trigger_views.xml',
        'views/menus.xml',
        'views/res_users_views.xml',
        'views/account_journal_views.xml',
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
        #wizard
        'wizard/account_move_debit_view.xml',
        #reports
        'reports/report_invoice.xml',
        #'views/pos_config_views.xml',
        #'views/pos_order_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
