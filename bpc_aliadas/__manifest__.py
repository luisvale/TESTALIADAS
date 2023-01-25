# -*- coding: utf-8 -*-
{
    'name': "bpc_aliadas",
    'summary': """
        Personalización ALIADAS""",
    'description': """
        Módulo personalizado para compañía ALIADAS
    """,
    'author': "Jhonny Mack Merino Samillán",
    'company': 'BPC LATAM',
    'website': "https://www.bpc-lat.com/",
    'category': 'Sales',
    'version': '15.0.13.6',
    # any module necessary for this one to work correctly
    'depends': ['base','hn_einvoice', 'purchase_requisition','purchase','sale','sale_renting','sale_subscription','account_budget','sales_team',
                'purchase_stock', 'approvals', 'purchase_requisition_stock','crm_helpdesk','website_helpdesk_form', 'hr'],
    # always loaded
    'data': [
        #security
        'security/groups.xml',
        'security/ir.model.access.csv',
        # data
        'data/approval_category_data.xml',
        'data/mail_activity_data.xml',
        'data/sequences.xml',
        'data/product.xml',
        'data/cron.xml',
        'data/payment_method_data.xml',
        'data/website_helpdesk.xml',
        'data/mail_template_approval_data.xml',


        #views
        'views/res_bank_views.xml',
        'views/purchase_requisition_views.xml',
        'views/res_users_views.xml',
        'views/product_classification_views.xml',
        'views/purchase_order_views.xml',
        'views/purchase_order_line_views.xml',
        'views/sale_order_checklist_views.xml',
        'views/documents_checklist_views.xml',
        'views/sale_order_views.xml',
        'views/res_partner_views.xml',
        'views/documents_checklist_views.xml',
        'views/documents_checklist_lines_partner_views.xml',
        'views/check_list_process_order.xml', #check list detallado de procesos
        'views/account_fiscal_position_views.xml',
        'views/sale_subscription_views.xml',
        'views/res_config_settings_views.xml',
        'views/account_budget_views.xml',
        'views/crm_views.xml',
        'views/crm_team_views.xml',
        'views/crm_lead_views.xml',
        'views/approval_views.xml',
        'views/approval_internal_line_views.xml',
        'views/approval_level_views.xml',
        'views/product_pricelist_views.xml',
        'views/account_move_views.xml',
        'views/product_views.xml',
        'views/subscription_history_views.xml',
        'views/maintenance_level_views.xml',
        'views/maintenance_periodic_views.xml',
        'views/maintenance_equipment_views.xml',
        'views/maintenance_equipment_tonnage_views.xml',
        'views/menus_views.xml',
        'views/account_payment_views.xml',
        'views/hr_deparment_authorization_line_views.xml',
        'views/hr_department_views.xml',
        'views/request_module_views.xml',
        'views/helpdesk_views.xml',  #add 04-01-23
        'views/hr_employee_views.xml',  #add 10-01-23
        'website/helpdesk_service.xml', #add 04-01-23
        'data/website_data.xml', #add 04-01-23

        #wizard
        'wizard/purchase_order_approved_wizard.xml',
        'wizard/purchase_make_invoice_advance_views.xml',
        'wizard/rental_configurator_views.xml',
        'wizard/sale_subscription_masive_wizard.xml',
        'wizard/account_payment_register_views.xml',
        #'wizard/mail_wizard_invite_views.xml',

        #report
        #'report/purchase_order_templates.xml',
        #'report/purchase_quotation_templates.xml',
        'report/report_invoice.xml', #Facturas, nota de crédito y débito
        'report/report_payment.xml', #Pagos
        'report/report_purchase_order.xml', #Orden de compra
        'report/report_paycheck.xml', #Pago de cheque
        'report/sale_report_templates.xml', #Presupuesto de ventas

        #data new
        #'data/purchase_mail_template_data.xml',
    ],
    'assets': {
		'web.report_assets_common': [
			'/bpc_aliadas/static/css/css_invoice.css',
		],
	},
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
