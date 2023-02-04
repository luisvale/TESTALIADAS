# -*- coding: utf-8 -*-
# Part of Browseinfo. See LICENSE file for full copyright and licensing details.
{
    'name': 'All in One Mass Cancel(Sales/Purchase/Invoice)',
    'version': '15.0.0.0',
    'author':'BrowseInfo',
    'category': 'Extra Tools',
    'sequence': 15,
    'summary': 'mass cancel purchase order mass cancel RFQ mass cancel sales order mass cancel invoice mass cancel quotation cancel multiple Sale Order cancel multiple invoice cancel multiple purchases cancel mass sales cancel multiple sale order cancel all in one cancel',
    'description': """Allow you to cancel the multiple Purchase Order

    mass cancel purchase order
    mass cancel purchases order
    mass cancel RFQ
    mass cancel request for quotation
    mass cancel quotation
    mass purchases cancel
    mass purchase cancel
    mass rfq cancel
    mass request for quotation cancel
    mass quotation cancel
    mass quotation order cancel
    mass purchase order cancel
    cancel mass purchase order
    cancel purchase order
    cancel mass rfq
    cancel mass purchases
    cancel mass quotation

Allow you to cancel the multiple Sale Order

    mass cancel sales order
    mass cancel sale order
    mass cancel Quotation
    mass cancel request for quotation
    mass cancel RFQ
    mass Sales cancel
    mass Sale cancel
    mass rfq cancel
    mass request for quotation cancel
    mass quotation cancel
    mass quotation order cancel
    mass Sale order cancel
    cancel mass sale order
    cancel sale order
    cancel mass rfq
    cancel mass sales
    cancel mass quotation

Allow you to cancel the invoice

    mass cancel invoices
    mass cancel customer invoice
    mass cancel vendor bills
    mass cancel supplier invoice
    mass cancel customer invoice
    mass invoice cancel
    mass vendor bills cancel
    mass vendor bill cancel
    mass customer invoice cancel
    mass customer invoices cancel
    mass vendor bill cancel
    mass vendor bills cancel
    cancel mass invoices
    cancel mass customer invoices
    cancel mass invoices
    cancel mass vendor bills
    cancel mass sales invoice
    multiple purchase order cancel
    multiple purchases order cancel
    multi purchase order cancel purchases revert purchases revert purchases order cancel purchase order
    cancel Request for Quotation cancel quote cancel RFQ cancel purchase cancel

        multiple sale order cancel
    multiple sales order cancel
    multi sale order cancel sales revert sales revert sales order cancel sale order
    cancel quotation cancel quote cancel Quotations cancel sales order

        multiple invoice cancel
    multi invoice cancel invoice revert invoice revert account invoice cancel account invoice
    cancel validated invoice cancel open invoice cancel validate invoice cancel orders

     """,
    "price": 25,
    "currency": 'EUR',
    'website': 'https://www.browseinfo.in',
    'depends': ['base','sale_management','purchase','account','stock','purchase_stock','sale_stock'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/wizard_views.xml',
        'wizard/wizard_view_purchase.xml',
        'wizard/wizard_view_invoice.xml',
        'views/views.xml',

        ],
    "license": "OPL-1",
    'css': [],
    'installable': True,
    'auto_install': False,
    'application': True,
    "images":['static/description/Banner.png'],
    "live_test_url":'https://youtu.be/Q7UGzibDH3E',
}
