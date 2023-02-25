# -*- coding: utf-8 -*-

from odoo import fields, models, api, _ 

class SalaryRecord(models.Model): 
    _name = 'salary.record'
    
    contract_id = fields.Many2one('hr.contract', 'Contrato')
    start_date = fields.Date('Fecha de Inicio')
    end_date = fields.Date('Fecha Final')
    salary = fields.Float('Salario')