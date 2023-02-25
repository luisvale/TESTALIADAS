# -*- coding: utf-8 -*-
{
    'name': 'Solicitud de bonos por aprobaciones',
    "author": "Ernesto García",
    'version': '15.0.1.3',
    'summary': "Se agrega nuevo tipo de aprovación",
    'description': """
    Se agrega nuevo tipo de aprovación
    """,
    "license": "OPL-1",
    'depends': ['approvals', 'hr_payroll'],
    'data': [
            'data/approval_category_data.xml',
            'views/approval_views.xml'
            ],
    'installable': True,
    'auto_install': False,
}
