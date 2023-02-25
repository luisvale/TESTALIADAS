# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, date

class HrEmployee(models.Model): 
    _inherit = 'hr.employee'
    
    check_list_lines = fields.One2many('employee.documents.check_list.lines', 'employee_id', domain=[('check_list_type','=','sale')])  #
    
    def get_check_list(self):
            for record in self:
                list = []
                check_list_actives = self.env['employee.documents.check_list'].sudo().search([('state_active', '=', True),
                                                                                    ('type', '=', 'sale'),
                                                                                    ('company_id', '=', record.env.company.id)])
                if check_list_actives:
                    for item in check_list_actives:
                        find = record.check_list_lines.filtered(lambda l:l.check_list_id.id == item.id)
                        if not find:
                            list.append((
                                0, 0, {
                                    'check_list_id': item.id,
                                    'date_due': item.date_due
                                }
                            ))
                    if list:
                        record.sudo().write({'check_list_lines': list})

                else:
                    raise ValidationError(_("No hay checklist de documentos activos."))