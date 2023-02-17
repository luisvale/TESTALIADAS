# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime, time

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)
from .. import maintenance

STATES = [('draft', 'Borrador'),
          ('pending', 'Espera de productos'),
          ('done', 'Procesando picking'),
          ('process', 'En Proceso'),
          ('finished', 'Terminado'),
          ('cancel', 'Cancelado'),
          ]

class MaintenancePeriodic(models.Model):
    _name = 'maintenance.periodic'
    _description = 'Aliadas : Mantenimiento'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc'
    _rec_name = 'name'

    name = fields.Char(string='Nombre', default='', store=True, readonly=1, copy=False)
    active = fields.Boolean(string='Activo', default=True)
    date_start = fields.Date('Fecha inicio', store=True, tracking=True)
    date_end = fields.Date('Fecha fin', store=True, tracking=True)
    priority = fields.Selection([('0', 'Very Low'), ('1', 'Baja'), ('2', 'Normal'), ('3', 'Alta')], string='Prioridad')
    description = fields.Char(string='Descripción')
    is_master = fields.Boolean(string='Tarea master')
    maintenance_type = fields.Selection([('corrective', 'Correctivo'), ('preventive', 'Preventivo')], string='Tipo')
    maintenance_team_id = fields.Many2one('maintenance.team', string='Equipo')
    color = fields.Integer("Color Index", default=0)
    user_id = fields.Many2one('res.users', string='Responsable')
    narration = fields.Text(string='Notas')
    periodicity_line_ids = fields.One2many('maintenance.periodicity.line', 'maintenance_id', copy=True)
    equipment_line_ids = fields.One2many('maintenance.equipment.line', 'maintenance_id', copy=True)
    material_line_ids = fields.One2many('maintenance.material.line', 'maintenance_id', copy=True)
    # analytic_line_ids = fields.Many2many('account.analytic.line', string='Tareas')
    analytic_line_ids = fields.One2many('account.analytic.line', 'maintenance_id', string='Tareas', copy=False)
    state = fields.Selection(STATES, string='Estado', default='draft', tracking=True)
    parent_id = fields.Many2one('maintenance.periodic', string='Origen')

    level_id = fields.Many2one('maintenance.level', string='Nivel', compute='_compute_level_id')

    @api.model
    def _default_origin(self):
        location = self.env['stock.location'].sudo().search([('company_id','=',self.env.company.id), ('maintenance_use','=','origin')], limit=1)
        return location

    @api.model
    def _default_destiny(self):
        location = self.env['stock.location'].sudo().search([('company_id','=',self.env.company.id), ('maintenance_use','=','destiny')], limit=1)
        return location

    location_init_id = fields.Many2one('stock.location', string='Locación origen', default=_default_origin)
    location_end_id = fields.Many2one('stock.location', string='Locación destino', default=_default_destiny)
    # Depende de los estado y los productos
    purchase_requisition_id = fields.Many2one('purchase.requisition', string='Licitación', tracking=True, copy=False)
    purchase_requisition_ids = fields.Many2many('purchase.requisition', string='Licitaciones')

    picking_id = fields.Many2one('stock.picking', string='Picking', tracking=True, copy=False)
    picking_ids = fields.Many2many('stock.picking', string="Picking's", tracking=True, copy=False)
    picking_count = fields.Integer(compute='_compute_picking_count')
    picking_line_add = fields.Boolean(compute='_compute_picking_line_add')

    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related="company_id.currency_id", string="Moneda", readonly=True, store=True, compute_sudo=True)
    total_cost_material = fields.Monetary(string='Costo materiales', store=True, compute='_compute_total')
    total_cost_work = fields.Monetary(string='Costo mano obra', store=True, compute='_compute_total')
    total_amount = fields.Monetary(string='Total', store=True, compute='_compute_total')

    def get_location_init_id(self):
        self.ensure_one()
        self.location_init_id = self._default_origin()

    def get_location_end_id(self):
        self.ensure_one()
        self.location_end_id = self._default_destiny()

    @api.depends('material_line_ids', 'material_line_ids.subtotal', 'analytic_line_ids.unit_amount','analytic_line_ids.employee_id',
                 'analytic_line_ids.contract_id')
    def _compute_total(self):
        for record in self:
            record.total_cost_material = sum(line.subtotal for line in record.material_line_ids)
            total_cost_work = 0.0
            for line in record.analytic_line_ids:
                if line.contract_id:
                    hours_total = line.contract_id.resource_calendar_id.full_time_required_hours * 4
                    total_by_hour = line.contract_id.wage / hours_total
                    cost = (total_by_hour * line.unit_amount) if line.unit_amount > 0.0 else 0
                    total_cost_work += cost
            record.total_cost_work = total_cost_work  # Pendiente
            record.total_amount = record.total_cost_material + record.total_cost_work

    def get_contract_by_employee(self):
        """Traer contratos de empleados"""
        for record in self:
            for line in record.analytic_line_ids:
                line._onchange_employee_id()

    def _get_name(self):
        if self.is_master:
            name = self.env.ref('bpc_aliadas.sequence_maintenance_master').next_by_id()
            if self.name in (False, ''):
                self.name = name
        else:
            name = self.env.ref('bpc_aliadas.sequence_maintenance_periodic').next_by_id()
            if self.name in (False, ''):
                self.name = name

    def state_cancel(self):
        self.state = 'cancel'

    def state_draft(self):
        self.state = 'draft'

    def state_pending(self):
        """Crear transferencia (picking) en inventario con los materiales. Es necesario configurar locación de salida.
        Si no hay crear licitación de compra"""
        if not self.is_master:
            self._get_name()
        process, msg = maintenance.requisition._eval_stock_products(self)
        if not process:
            if msg not in (False, ''):
                raise ValidationError(_(msg))
            else:
                self.state = 'pending'
        else:
            self.state_done()
            #self.state = 'done'

    def consult_stock(self):
        """Consulta esto solo cunado el estado es PENDING"""
        lines = maintenance.requisition._eval_stock(self)
        if lines:
            raise ValidationError(_("Aún hay líneas con stock en cero."))
        else:
            self.state_done()

    def state_done(self):
        "También servirá para crear nuevo picking"
        "Productos realizados"
        """Crear un CRON PARA ESTO, y ver si tenemos stock(Esto lo evaluamos con la VALIDACIÓN DEL picking)"""
        #self.consult_stock()
        process, error = maintenance.picking._eval_products(self)
        if process:
            self.state = 'done'
        else:
            raise ValidationError(_(error))

    def state_process(self):
        "En proceso"
        """Ingresar tiempo en hojas de horas"""
        if self.is_master:
            self._get_name()
        else:
            if not self.picking_id:
                raise ValidationError(_("Debería haber un picking relacionado"))
            if self.picking_id.state != 'done':
                raise ValidationError(_("El picking %s no ha sido validado aún, debería estar en estado REALIADO para seguir con el proceso." % self.picking_id.name))
        self.state = 'process'


    def state_finished(self):
        """Evluar horas en cero"""
        lines_analytic = self.analytic_line_ids.filtered(lambda l: l.unit_amount <= 0.0)
        if lines_analytic:
            raise ValidationError(_("En la sección tareas no puede tener líneas con horas reales en cero."))
        self.state = 'finished'

    @api.depends('analytic_line_ids')
    def _compute_level_id(self):
        for record in self:
            level_ids = record.analytic_line_ids.mapped('level_id')
            if level_ids:
                record.level_id = level_ids[0]
            else:
                record.level_id = False

    @api.model
    def _cron_maintenance_periodic(self):
        _logger.info("Ejecutando CRON _cron_maintenance_periodic")
        #masters = self.sudo().search([('is_master','=',True),('state','=','process'),('active','=',True),('id','=',4)])
        masters = self.sudo().search([('is_master', '=', True), ('state', '=', 'process'), ('active', '=', True)])
        for master in masters:
            _logger.info("ALIADAS: Evaluando master name %s " % master.name)
            if master.date_end <= datetime.now().date():
                _logger.info("ALIADAS: Tarea master venció el %s " % master.date_end)
            else:
                res = maintenance.periodic_level.eval_periodic_child(master)
                _logger.info("ALIADAS: Respuesta - %s " % res)


    def complete_data(self):
        self.ensure_one()
        res = maintenance.periodic_level_manual.eval_periodic_child(self)
        _logger.info("ALIADAS: Respuesta - %s " % res)

    @api.onchange('parent_id')
    def _onchange_parent_id(self):
        for record in self:
            if record.parent_id:
                record.location_init_id = record.parent_id.location_init_id
                record.location_end_id = record.parent_id.location_end_id
            # else:
            #     record.location_init_id = False
            #     record.location_end_id = False
            #     print("FFF")

    def _compute_picking_count(self):
        for record in self:
            record.picking_count = len(record.picking_ids.ids)

    #@api.depends('material_line_ids')
    def _compute_picking_line_add(self):
        for record in self:
            picking_line_add = False
            m_line = record.material_line_ids.filtered(lambda l: l.quantity_add > 0)
            if m_line:
                picking_line_add = True
            record.picking_line_add = picking_line_add

    def create_new_picking(self):
        "También servirá para crear nuevo picking"
        "Productos realizados"
        """Crear un CRON PARA ESTO, y ver si tenemos stock(Esto lo evaluamos con la VALIDACIÓN DEL picking)"""
        # self.consult_stock()
        process, error = maintenance.picking._eval_products(self, process_qty_news=True)
        if process:
            _logger.info("Procesando : %s" % process)
            self._compute_picking_line_add()

        else:
            raise ValidationError(_(error))

    def view_all_picking(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'views': [(False, 'list'), (False, 'form')],
            'view_mode': 'list,form',
            'target': 'current',
            'name': 'Transferencias de Mantenimiento %s ' % self.name,
            'domain': [('id', 'in', self.picking_ids.ids)],
        }