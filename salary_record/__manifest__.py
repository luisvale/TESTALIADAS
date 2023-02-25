# -*- coding: utf-8 -*-

{
    'name' : "Historial de salario", 
    'category' : "Human Resources", 
    'summary' : """
    Historial de salario
    """,
    'depends' : [
        'hr_payroll',
    ],
    'data' : [
        'security/ir.model.access.csv',  
        'views/hr_contract_views.xml',
    ], 
    'installable' : True, 
    'auto_install' : False
}