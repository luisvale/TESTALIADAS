# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    code = fields.Char(string='Código')

    def generate_code(self):
        self.ensure_one()
        hr_employee_sequence_id = self.company_id.hr_employee_sequence_id
        if not hr_employee_sequence_id:
            raise ValidationError(_("Asegúrese de asignar una secuencia para códigos de empleados en la configuración del módulo de empleados."))

        new_code = hr_employee_sequence_id.next_by_id()
        self.sudo().write({'code': new_code})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': _('Bien!'),
                'message': _("Se ha generaco el código correctamente."),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
