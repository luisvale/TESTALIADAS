# -*- coding: utf-8 -*-

{
    'name' : "Checklist Empleados", 
    'category' : "Human Resources", 
    'summary' : """
    Checklist empleados
    """,
    'depends' : [
        'hr',
    ],
    'data' : [
        'security/ir.model.access.csv',  
        'views/hr_employee_views.xml',  
        'views/documents_checklist_views.xml',
        'views/documents_checklist_lines_partner_views.xml',
    ], 
    'installable' : True, 
    'auto_install' : False
}