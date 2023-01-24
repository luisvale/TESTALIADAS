# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime, time

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from .. import maintenance

class MaintenancePeriodicityLine(models.Model):
    _name = 'maintenance.periodicity.line'
    _description = 'Aliadas: Periodicidad en niveles de mantenimiento'

    maintenance_id = fields.Many2one('maintenance.periodic')
    level_id = fields.Many2one('maintenance.level', string='Nivel')
    days = fields.Integer(string='Días')
    interval = fields.Integer(string='Intervalo final', help='dias para la fecha final')
    interval_start = fields.Integer(help='Días para la fecha de inicio')


class MaintenanceEquipmentLine(models.Model):
    _name = 'maintenance.equipment.line'
    _description = 'Aliadas: Equipos para mantenimiento'

    maintenance_id = fields.Many2one('maintenance.periodic')
    maintenance_state = fields.Selection(related='maintenance_id.state')
    maintenance_is_master = fields.Boolean(related='maintenance_id.is_master')
    equipment_id = fields.Many2one('maintenance.equipment', string='Equipo')
    note = fields.Char(string='Observación')


MODE = [('in_purchase', 'Procesando orden compra'), ('stock', 'Contiene stock')]
class MaintenanceMaterialLine(models.Model):
    _name = 'maintenance.material.line'
    _description = 'Aliadas: Lista de materiales para mantenimiento'

    maintenance_id = fields.Many2one('maintenance.periodic')
    product_id = fields.Many2one('product.template', string='Producto')
    uom_id = fields.Many2one('uom.uom', related='product_id.uom_id', readonly=True, string='Und.Medida')
    warehouse_ids = fields.Many2many('stock.warehouse', related='product_id.warehouse_ids')
    warehouse_id = fields.Many2one('stock.warehouse', string='Almacén')
    stock = fields.Float(string='Disponible', compute='_compute_stock')
    mode = fields.Selection(MODE, string='Estado')
    currency_id = fields.Many2one('res.currency', string='Moneda')
    quantity = fields.Float(string='Cantidad')
    cost = fields.Monetary(string='Costo')
    subtotal = fields.Monetary(string='Subtotal', compute='_compute_subtotal', store=True)

    @api.depends('quantity', 'cost')
    def _compute_subtotal(self):
        for record in self:
            record.subtotal = record.cost * record.quantity

    @api.depends('warehouse_id')
    def _compute_stock(self):
        for record in self:
            stock = 0.0
            if record.product_id and record.warehouse_id:
                lot_stock_id = record.warehouse_id.lot_stock_id
                wh_input_stock_loc_id = record.warehouse_id.wh_input_stock_loc_id
                quants = self.env['stock.quant'].sudo().search([('product_tmpl_id', '=', record.product_id.id),
                                                                ('location_id','in', (lot_stock_id.id,wh_input_stock_loc_id.id))])
                stock = sum(l.quantity for l in quants)
            record.stock = stock

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for record in self:
            if record.product_id:
                record.cost = record.product_id.standard_price
