# -*- coding: utf-8 -*-

import ast

from datetime import date, datetime, timedelta

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT

class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'

    maintenance_p_count = fields.Integer(compute='_compute_maintenance_periodic_count', store=True)

    tonnage_id = fields.Many2one('maintenance.equipment.tonnage', string='Tonelaje')

    def _compute_maintenance_periodic_count(self):
        for record in self:
            maintenance_p_count = 0
            lines = record.env['maintenance.equipment.line'].sudo().search([('equipment_id','=',record.id),('maintenance_is_master','=',False)])
            if lines:
                maintenance_ids = lines.mapped('maintenance_id')
                maintenance_p_count = len(maintenance_ids.ids)
            record.maintenance_p_count = maintenance_p_count


    def view_maintenance_periodic_list(self):
        pass