# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ReturnPicking(models.TransientModel):
    _inherit = 'stock.return.picking'

    def _prepare_picking_default_values(self):
        vals = super(ReturnPicking, self)._prepare_picking_default_values()
        self._find_maintenance(vals)
        return {
            'move_lines': [],
            'picking_type_id': self.picking_id.picking_type_id.return_picking_type_id.id or self.picking_id.picking_type_id.id,
            'state': 'draft',
            'origin': _("Return of %s") % self.picking_id.name,
            'location_id': self.picking_id.location_dest_id.id,
            'location_dest_id': self.location_id.id
        }

    def _find_maintenance(self, vals):
        if self.picking_id.maintenance_id:
            vals['maintenance_id'] = self.picking_id.maintenance_id.id
        elif vals['origin']:
            maintenance_id = self.env['maintenance.periodic'].sudo().search([('name', '=', self.picking_id.origin), ('company_id', '=', self.picking_id.company_id.id)])
            if maintenance_id:
                vals['maintenance_id'] = maintenance_id.id
                if not self.picking_id.maintenance_id:
                    self.picking_id.maintenance_id = maintenance_id

    def create_returns(self):
        res = super(ReturnPicking, self).create_returns()
        self._assign_picking_to_maintenance(res)
        return res

    def _assign_picking_to_maintenance(self, res):
        if 'res_id' in res:
            stock_picking_id = self.env['stock.picking'].sudo().browse(res['res_id'])
            if stock_picking_id and stock_picking_id.maintenance_id:
                maintenance_id = stock_picking_id.maintenance_id
                maintenance_id.picking_ids += stock_picking_id
