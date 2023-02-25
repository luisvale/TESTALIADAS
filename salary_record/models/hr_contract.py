# -*- coding: utf-8 -*-

from odoo import fields, models, api, _ 

class HrContract(models.Model): 
    _inherit = 'hr.contract'
    
    salary_record_ids = fields.One2many('salary.record', 'contract_id')