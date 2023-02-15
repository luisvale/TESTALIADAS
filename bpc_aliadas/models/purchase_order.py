# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime, time, timedelta
from dateutil.relativedelta import relativedelta
from functools import partial
from itertools import groupby
import json

from markupsafe import escape, Markup
from pytz import timezone, UTC
from werkzeug.urls import url_encode
from collections import defaultdict

from odoo import api, fields, models, _, SUPERUSER_ID
from odoo.osv import expression
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.misc import formatLang, get_lang, format_amount
from odoo.tests.common import TransactionCase, tagged, Form

import logging

_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    commercial_ids = fields.One2many(related='partner_id.commercial_ids')
    commercial_id = fields.Many2one('res.partner.commercial', string='Nombre comercial')
    currency_rate = fields.Float("Currency Rate", compute='_compute_currency_rate', compute_sudo=True, store=True,  digits='Purchase change rate',
                                 readonly=True, help='Ratio between the purchase order currency and the company currency')

    @api.depends('currency_id')
    def _compute_currency_rate(self):
        for record in self:
            currency_rate = 1
            if record.company_id.currency_id != record.currency_id:
                currency_rate = record.currency_id._convert(1, record.company_id.currency_id, record.company_id, record.date_order.date() or datetime.now().date())
            record.currency_rate = currency_rate

    state = fields.Selection([
        ('bidding', 'Proceso licitación'),
        ('evaluation', 'Evaluación de presupuesto'),  # custom
        ('draft', 'RFQ'),
        ('on_hold', 'En espera'),
        ('pending', 'Esperando aprobación'),
        ('approved', 'Aprobada'),
        ('sent', 'RFQ Sent'),
        ('to approve', 'To Approve'),
        ('purchase', 'Purchase Order'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled')
    ], string='Status', readonly=True, index=True, copy=False, default='bidding', tracking=True)
    get_purchase = fields.Boolean(compute='_compute_get_purchase', copy=False)
    purchase_o_ids = fields.Many2many('purchase.order', 'purchase_requisition_id_purchase_rel', 'purchase_o_id', 'purchase_second_id', copy=False)
    approved = fields.Boolean(string='Aprobado', copy=False)

    # Evaluación de presupuesto
    force_budget = fields.Boolean(string='Forzar paso de evaluación de presupuesto', tracking=True, copy=False)
    #limit_budget = fields.Boolean(help='Paso el límite de prespuesto', tracking=True, copy=False, readonly=False, compute='_compute_limit_budget')
    limit_budget = fields.Boolean(help='Paso el límite de prespuesto', tracking=True, copy=False, readonly=False)
    message_budget = fields.Text(store=True)
    exist_budget = fields.Boolean(compute='_compute_exist_budget', string='Existe presupuesto?', store=True, tracking=True)

    # Anticipo por aprobación
    approval_request_advance = fields.Many2one('approval.request', string='Aprobación de anticipo', copy=False)
    approval_request_advance_status = fields.Selection(related='approval_request_advance.request_status', store=True, copy=False)
    # Anticipo automático desde proveedor
    advance_check = fields.Boolean(string='Aplica anticipo', help='Aplicación de anticipo solo a proveedores')  # P2 - Anticipo
    advance_payment_method = fields.Selection([('percentage', 'Porcentaje'), ('fixed', 'Monto fijo')], string='Tipo anticipo', default='percentage')  # P2 - Anticipo
    advance_amount = fields.Float(string='Monto anticipo')  # P2 - Anticipo

    # Aprobaciones
    approval_request_ids = fields.Many2many('approval.request', string='Solicitudes', copy=False)
    approval_pending_count = fields.Float(compute='_compute_approval_required', copy=False, string='Pendientes')
    approval_approved_count = fields.Float(compute='_compute_approval_required', copy=False, string='Aprobadas')
    approval_cancel_count = fields.Float(compute='_compute_approval_required', copy=False, string='Canceladas/En espera')

    requisition_request_id = fields.Many2one('approval.request', related='requisition_id.request_id', readonly=False, store=True)
    requisition_request_status = fields.Selection(related='requisition_request_id.request_status', readonly=False, store=True)

    amount_total_without_check = fields.Monetary(string='Total compra', store=True, readonly=True, compute='_amount_all')

    force_purchase = fields.Boolean(string='Pedido forzado', help='Pasar a pedido de compra de forma forzada', copy=False)

    department_id = fields.Many2one('hr.department', string='Departamento')

    force_picking = fields.Boolean(string='Incluir picking')
    force_cancel = fields.Boolean(string='Cancelación forzada')

    send_mail_request = fields.Boolean(string='Envío mail aprobación', tracking=True)


    @api.constrains('advance_check', 'advance_amount')
    def _constraint_advance_check(self):
        for order in self:
            if order.advance_check:
                if order.advance_payment_method == 'percentage' and order.advance_amount > 100:
                    raise ValidationError(_("Para aplicación de anticipo por porcentaje el monto a aplicar no debe ser mayor a 100"))

    @api.depends('requisition_id', 'requisition_id.purchase_line_ids')
    def _compute_get_purchase(self):
        for record in self:
            if record.requisition_id:
                purchase_line_ids = record.requisition_id.purchase_line_ids
                if purchase_line_ids:
                    purchase_o_ids = purchase_line_ids - record
                    record.purchase_o_ids = purchase_o_ids
                record.department_id = record.requisition_id.department_id
            record.get_purchase = True

    def button_cancel(self):
        super(PurchaseOrder, self).button_cancel()
        self._unlink_from_budget()

    def button_cancel_force(self):
        for order in self:
            for inv in order.invoice_ids:
                if inv and inv.state not in ('cancel', 'draft'):
                    raise UserError(_("No se puede cancelar esta orden de compra. Primero debe cancelar las facturas de proveedores relacionadas."))

        self.write({'state': 'cancel', 'mail_reminder_confirmed': False})
        self._unlink_from_budget()

    def action_view_budget_lines(self):
        self.ensure_one()
        budget_lines = self.env['crossovered.budget.lines'].sudo()
        _find_budgets = self._find_budget_by_line()
        for line in _find_budgets:
            if line['budget']:
                budget_lines += line['budget']

        if budget_lines:
            return {
                'name': _('Presupuestos de orden de compra %s ' % self.name),
                'view_mode': 'list',
                'res_model': 'crossovered.budget.lines',
                # 'view_id': self.env.ref('bpc_aliadas.move_line_history_tree').id,
                'views': [(self.env.ref('account_budget.view_crossovered_budget_line_tree').id, 'list')],
                'type': 'ir.actions.act_window',
                'target': 'current',
                'domain': [('id', 'in', budget_lines.ids)],
                'context': {'expand': True, 'create': False, 'fsm_mode': True}
            }
        else:
            raise ValidationError(_("No hay líneas relacionadas a presupuesto"))

    def _find_budget_by_line(self):
        self.ensure_one()
        budget_lines = self.env['crossovered.budget.lines'].sudo().search([('purchase_line_ids', '!=', False)])
        _find = []
        for line in self.order_line:
            b_line = budget_lines.filtered(lambda b: line.id in b.purchase_line_ids.ids)
            if b_line:
                _find.append({'line': line, 'budget': b_line})
            else:
                _find.append({'line': line, 'budget': False})
        return _find

    def button_budget_force(self):
        for record in self:
            #ANTES DE ASIGNAR PRESUPUESTOS, BUSCAR SI TIENEN O NO
            _find_budgets = record._find_budget_by_line()
            lines = self.env['purchase.order.line']
            for line in _find_budgets:
                if not line['budget']:
                    pol = line['line']
                    _logger.info("Linea con ID %s y producto %s necesita presupuesto" % (pol.id, pol.product_id.name))
                    lines += pol

            if not lines:
                _logger.info("ALIADAS: Al parecer todas las líneas.")
                continue

            process, notes = record.sudo()._eval_budget(lines=lines)
            # note => ok, no_find, limit
            _logger.info("ALIADAS: Continuar con el proceso luego de la asignación de presupuestos ? %s " % process)
            if process:
                no_find = 0
                for note in notes:
                    if note == 'no_find':
                        no_find += 1

                if no_find == len(notes) and no_find > 0:
                    type_note = 'info'
                    title = 'Observación'
                    message = _("No se encontraron presupuestos")
                else:
                    type_note = 'success'
                    title = 'Bien!'
                    message = _("Se asignaron todas las líneas a presupuestos de forma correcta")
            else:
                line_limit_budget = record.order_line.filtered(lambda l: l.limit_budget)
                type_note = 'warning'
                title = 'Observación'
                message = _("Hay %s líneas que no fueron asigandas a un presupuesto por límite." % len(line_limit_budget))

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': type_note,
                    'title': title,
                    'message': message,
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }


    def button_reprocess(self):
        self.ensure_one()
        _logger.info("Cancelando de forma forzada")
        self.button_cancel_force()
        if self.approval_request_ids:
            _logger.info("Desvinculando aprobaciones: Cantidad de: %s" % len(self.approval_request_ids.ids))
            self.write({'approval_request_ids': [(3, app.id, 0) for app in self.approval_request_ids]})
        self.sudo().write({'state': 'bidding', 'approved': False})
        self.sudo().write({'send_mail_request': False})

    @api.ondelete(at_uninstall=False)
    def _unlink_if_cancelled(self):
        for order in self:
            if not order.state in ('cancel', 'bidding'):
                raise UserError(_('In order to delete a purchase order, you must cancel it first.'))

    def _unlink_from_budget(self):
        for record in self:
            for line in record.order_line:
                budget_line = self.env['crossovered.budget.lines'].sudo().search([('purchase_line_ids', 'in', line.ids)])
                if budget_line:
                    for bl in budget_line:
                        _logger.info("ALIADAS: Eliminación de línea con ID %s de la línea de prespuesto %s " % (line.id, bl.id))
                        bl.sudo().write({'purchase_line_ids': [(3, line.id)]})
                        # Reactualización de montos
                        bl.sudo()._update_reserved_amount_total()

    def button_evaluation_to_draft(self):
        for record in self:
            process, note = record.sudo()._eval_budget()
            if not process:
                record.sudo()._create_request('purchase_budget')
                record.sudo().write({'state': 'evaluation', 'limit_budget': True})
            else:
                _logger.info("Proceso de evaluación de presupuesto (Wizard) : %s" % process)
                record.sudo().write({'state': 'draft'})

            # _logger.info("ALIADAS : Pasar a estado draft forzando presupuesto")
            # if record.limit_budget:
            #     process = record.sudo()._eval_budget()
            #     _logger.info("Proceso de evaluación de presupuesto : %s" % process)
            #     record.sudo().write({'force_budget': True, 'state': 'draft'})
            #     # return record.show_approval_wizard()
            # else:
            #     record.sudo().write({'state': 'draft'})

    def button_bidding_to_draft(self):
        for record in self:
            _logger.info("ALIADAS : Pasar a estado draft")
            record.sudo().write({'state': 'draft'})
            return record.show_approval_wizard()
            # process = record._eval_budget()
            # if process and not record.approved:
            #     return record.show_approval_wizard()
            # if record.env.user.has_group('bpc_aliadas.group_purchase_order_bidding_to_draft'):
            #     record.sudo().write({'state': 'draft'})
            # else:
            #     raise UserError(_("Ud no tiene permiso para pasar esta orden de compra a estado PETICIÓN DE PRESUPUESTO."))

    def button_draft_to_bidding(self):
        for record in self:
            _logger.info("ALIADAS : Pasar a estado bidding")
            record.sudo().write({'state': 'bidding'})
            if record.order_line:
                for line in record.order_line:
                    line.sudo().write({'limit_budget': False})
                    budget_lines = self.env['crossovered.budget.lines'].sudo().search([('purchase_line_ids', 'in', line.ids)])
                    if budget_lines:
                        budget_lines.purchase_line_ids = budget_lines.purchase_line_ids - line

    def show_approval_wizard(self):
        if not self.approved:
            view = self.env.ref('bpc_aliadas.view_purchase_order_approved_wizard')
            return {
                'name': 'Aprobación de Orden de Compra',
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'purchase.order.approved.wizard',
                'views': [(view.id, 'form')],
                'view_id': view.id,
                'target': 'new',
                'context': dict(default_order_id=self.id),
            }


    def button_exist_budget(self):
        self.ensure_one()
        self._compute_exist_budget()

    def _compute_exist_budget(self):
        for record in self:
            exist_budget = False
            if not record.force_purchase:
                if record.exist_budget:
                    exist_budget = record.exist_budget
                else:
                    exist_budget = record._find_budget(button=True)
            record.exist_budget = exist_budget

    def _find_budget(self, button=True):
        self.ensure_one()
        _next = True
        message = ''
        order = self
        #for order in self:
        date_order = order.date_order
        date_order_timedelta = date_order - timedelta(hours=6)
        for line in order.order_line:
            account_id = line.account_id
            analytic_id = line.account_analytic_id
            crossovered_budget_lines = self.env['crossovered.budget.lines'].sudo().search([('analytic_account_id', '=', analytic_id.id),
                                                                                           ('check_control', '=', True),
                                                                                           ('general_budget_id', '!=', False)])

            budget_line = crossovered_budget_lines.filtered(lambda l: l.date_from <= date_order_timedelta.date() and l.date_to >= date_order_timedelta.date()
                                                                      and account_id.id in l.general_budget_id.account_ids.ids)
            if not budget_line:
                message += 'No se encontró presupuesto con cuenta analítica *%s*  y cuenta contable *%s* para la fecha *%s* ' % (analytic_id.name, account_id.name, date_order.date())
                order.sudo().write({'state': 'on_hold', 'message_budget': message})
                _next = False
            else:
                if button:
                    order.sudo().button_evaluation_to_draft()

        _logger.info("ALIADAS: Existe presupuesto %s " % _next)

        return _next


    def _eval_budget(self, lines=False):
        self.ensure_one()
        date_order = self.date_order
        process = True
        order_line = self.order_line if not lines else lines
        notes = []
        for line in order_line:
            if not line.check_purchase:
                _logger.info("ALIADAS : Línea con producto %s no procede a evaluación de presupuesto" % line.product_id.name)
                continue
            limit_budget = False
            if line.account_analytic_id:
                _logger.info("ALIADAS : Se analizará presupuesto para la cuenta anlítica - %s" % line.account_analytic_id.name)
                limit_budget, note = self.env['crossovered.budget.lines'].sudo()._find_analytic_line(line, date_order)
                _logger.info("LLegó a limite de presupuesto %s - nota %s" % (limit_budget, note))
                notes.append(note)
                #note => ok, no_find, limit
                _logger.info("ALIADAS - Response _find_analytic_line %s " % limit_budget)
            line.limit_budget = limit_budget

        line_limit_budget = order_line.filtered(lambda l: l.limit_budget)
        if line_limit_budget:
            process = False
        return process, notes

    # # TODO: *************** APROBACIÓN DE PRESUPUESTO ******************
    # @api.depends('order_line', 'order_line.limit_budget')
    # def _compute_limit_budget(self):
    #     for record in self:
    #         limit_budget = False
    #         if record.order_line:
    #             line_limit_budget = record.order_line.filtered(lambda l: l.limit_budget)
    #             if line_limit_budget:
    #                 limit_budget = True
    #         record.limit_budget = limit_budget
    #         # Si al menos una linea tiene limite de presupuesto, entonces la orden para a EVALUACION
    #         if limit_budget:
    #             _logger.info("ALIADAS: Pasará a estado de EVALUACIÓN")
    #             record.sudo().write({'state': 'evaluation'})

    def action_continue_process(self):
        for order in self:
            purchase_approved = order.approval_request_ids.filtered(lambda a: a.approval_type == 'purchase_approved')
            #Si no encuentra una aprobación general de compra, quiere decir que pasó por un proceso de aprobación de presupuesto
            if not purchase_approved:
                order.sudo().button_confirm()
            else:
                order._add_supplier_to_product()
                order.write({'state': 'purchase', 'date_approve': fields.Datetime.now()})
                order.filtered(lambda p: p.company_id.po_lock == 'lock').write({'state': 'done'})
                if order.partner_id not in order.message_partner_ids:
                    order.message_subscribe([order.partner_id.id])
                order._create_picking()
        return True

    def refresh_state(self):
        self._compute_approval_required()
        self.case_evaluation()
        form = Form(self)
        form.save()


    def case_evaluation(self):
        if self.state == 'evaluation':
            approved_count_ids = self.approval_request_ids.filtered(lambda l: l.request_status == 'approved')
            approved_count = len(approved_count_ids.ids)
            if len(self.approval_request_ids.ids) == approved_count:
                self.sudo().write({'state': 'draft'})

    def button_confirm(self):
        for order in self:
            if order.state != 'approved':
                order._create_request('purchase_approved')
                order.sudo().write({'state': 'pending'})
            else:
                return super(PurchaseOrder, self).button_confirm()

    # TODO: *************** CREACIÓN DE ANTICIPOS ******************
    def action_create_invoice(self):
        process_normal = self._eval_advance()
        if type(process_normal) != dict:
            return super(PurchaseOrder, self).action_create_invoice()
        else:
            return process_normal

    def _eval_advance(self):
        """Evaluación de anticipos de proveedor"""
        if self.advance_check:
            advance_amount = self.advance_amount
            if advance_amount <= 0.0:
                raise ValidationError(_("Asegúrese que el monto de anticipio sea mayor a cero"))
            if self.advance_payment_method == 'percentage' and advance_amount > 100:
                raise ValidationError(_("Para aplicación de anticipo por porcentaje el monto a aplicar no debe ser mayor a 100"))

            view = self.env.ref('bpc_aliadas.view_purchase_advance_payment_inv')

            has_down_payments = self.order_line.filtered(lambda line: line.is_downpayment)

            context = {
                'active_ids': self.ids,
                'default_purchase_id': self.ids[0],
            }
            if not has_down_payments:
                context['default_advance_payment_method'] = self.advance_payment_method
                context['default_amount'] = advance_amount

            return {
                'name': 'Crear factura',
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'purchase.advance.payment.inv',
                'view_id': view.id,
                'target': 'new',
                'context': context,
            }

        elif self.approval_request_advance:
            if self.approval_request_advance_status != 'approved':
                raise ValidationError(_("Esta orden de compra está ligada a la solicitud de aprobación %s , sin embargo aún no cuenta "
                                        "con la aprobación de los autorizadores." % self.approval_request_advance.name))
            else:
                view = self.env.ref('bpc_aliadas.view_purchase_advance_payment_inv')
                return {
                    'name': 'Crear factura',
                    'type': 'ir.actions.act_window',
                    'view_mode': 'form',
                    'res_model': 'purchase.advance.payment.inv',
                    'view_id': view.id,
                    'target': 'new',
                    'context': dict(active_ids=self.ids, default_purchase_id=self.ids[0]),
                }
        else:
            return True

    @api.depends('approval_request_ids', 'approval_request_ids.request_status')
    def _compute_approval_required(self):
        for record in self:
            pending_count = 0
            approved_count = 0
            cancel_count = 0
            if record.approval_request_ids:
                pending_count_ids = record.approval_request_ids.filtered(lambda l: l.request_status == 'pending')
                approved_count_ids = record.approval_request_ids.filtered(lambda l: l.request_status == 'approved')
                cancel_count_ids = record.approval_request_ids.filtered(lambda l: l.request_status in ('refused', 'cancel'))
                pending_count = len(pending_count_ids.ids)
                approved_count = len(approved_count_ids.ids)
                cancel_count = len(cancel_count_ids.ids)
                if len(record.approval_request_ids.ids) == approved_count and record.state == 'pending':
                    record.state = 'approved'
            record.approval_pending_count = pending_count
            record.approval_approved_count = approved_count
            record.approval_cancel_count = cancel_count

    def _create_request(self, approval_type):
        _logger.info("ALIADAS: Compras - Aprobación de tipo %s " % approval_type)
        # category_id = self.env.ref('bpc_aliadas.approval_category_data_purchase_general').id
        category_id = self.env['approval.category'].sudo().search([('approval_type', '=', approval_type), ('company_id', '=', self.company_id.id)], limit=1)
        #category_id = self.env['approval.category'].sudo().search([('approval_type', '=', 'purchase_approved'), ('company_id', '=', self.company_id.id)], limit=1)
        if category_id:
            _request = self.env['approval.request'].create({
                'category_id': category_id.id,
                'date_start': fields.Datetime.now(),
                'date_end': fields.Datetime.now(),
                'partner_id': self.env.user.partner_id.id,
                'reference': self.name,
                'origin': self.name,
                'purchase_id': self.id,
                'request_owner_id': self.env.user.id,
                'department_id': self.department_id.id if self.department_id else False
            })
            if _request:
                self.approval_request_ids += _request
                _request.sudo().action_confirm()

    def _get_invoiceable_lines(self, final=False):
        """Return the invoiceable lines for order `self`."""
        down_payment_line_ids = []
        invoiceable_line_ids = []
        pending_section = None
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')

        for line in self.order_line:

            # Personalizado para aliadas
            if not line.check_purchase and not line.is_downpayment:
                continue
            # Fin

            if line.display_type == 'line_section':
                # Only invoice the section if one of its lines is invoiceable
                pending_section = line
                continue
            if line.display_type != 'line_note' and float_is_zero(line.qty_received, precision_digits=precision) and not line.is_downpayment:
                continue
            if line.qty_received > 0 or (line.qty_received <= 0 and final) or line.display_type == 'line_note':
                if line.is_downpayment:
                    # Keep down payment lines separately, to put them together
                    # at the end of the invoice, in a specific dedicated section.
                    down_payment_line_ids.append(line.id)
                    continue
                if pending_section:
                    invoiceable_line_ids.append(pending_section.id)
                    pending_section = None
                invoiceable_line_ids.append(line.id)

        return self.env['purchase.order.line'].browse(invoiceable_line_ids + down_payment_line_ids)

    def _prepare_invoice(self):
        res = super(PurchaseOrder, self)._prepare_invoice()
        res['document_type_purchase_id'] = self.env.ref('hn_einvoice.document_factura_electronica').id
        res['purchase_id'] = self.ids[0] if len(self.ids) > 0 else False
        return res

    def action_create_invoice_delivered(self, final):
        """Create the invoice associated to the PO.
        """
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')

        # 1) Prepare invoice vals and clean-up the section lines
        invoice_vals_list = []
        invoice_item_sequence = 0  # Incremental sequencing to keep the lines order on the invoice
        sequence = 10
        for order in self:

            order = order.with_company(order.company_id)
            pending_section = None
            # Invoice values.
            invoice_vals = order._prepare_invoice()
            invoiceable_lines = order._get_invoiceable_lines(final)

            if not any(not line.display_type for line in invoiceable_lines):
                continue

            invoice_line_vals = []
            down_payment_section_added = False
            for line in invoiceable_lines:
                if not down_payment_section_added and line.is_downpayment:
                    # Create a dedicated section for the down payments
                    # (put at the end of the invoiceable_lines)
                    invoice_line_vals.append(
                        (0, 0, order._prepare_down_payment_section_line(
                            sequence=invoice_item_sequence,
                        )),
                    )
                    down_payment_section_added = True
                    invoice_item_sequence += 1

                prepare_line = line._prepare_account_move_line()
                prepare_line.update({'sequence': invoice_item_sequence})
                invoice_line_vals.append((0, 0, prepare_line), )
                invoice_item_sequence += 1

            invoice_vals['invoice_line_ids'] += invoice_line_vals
            invoice_vals_list.append(invoice_vals)

        # 2) group by (company_id, partner_id, currency_id) for batch creation
        new_invoice_vals_list = []
        for grouping_keys, invoices in groupby(invoice_vals_list, key=lambda x: (x.get('company_id'), x.get('partner_id'), x.get('currency_id'))):
            origins = set()
            payment_refs = set()
            refs = set()
            ref_invoice_vals = None
            for invoice_vals in invoices:
                if not ref_invoice_vals:
                    ref_invoice_vals = invoice_vals
                else:
                    ref_invoice_vals['invoice_line_ids'] += invoice_vals['invoice_line_ids']
                origins.add(invoice_vals['invoice_origin'])
                payment_refs.add(invoice_vals['payment_reference'])
                refs.add(invoice_vals['ref'])
            ref_invoice_vals.update({
                'ref': ', '.join(refs)[:2000],
                'invoice_origin': ', '.join(origins),
                'payment_reference': len(payment_refs) == 1 and payment_refs.pop() or False,
            })
            new_invoice_vals_list.append(ref_invoice_vals)
        invoice_vals_list = new_invoice_vals_list

        # 3) Create invoices.
        moves = self.env['account.move']
        AccountMove = self.env['account.move'].with_context(default_move_type='in_invoice')
        for vals in invoice_vals_list:
            moves |= AccountMove.with_company(vals['company_id']).create(vals)

        # 4) Some moves might actually be refunds: convert them if the total amount is negative
        # We do this after the moves have been created since we need taxes, etc. to know if the total
        # is actually negative or not
        moves.filtered(lambda m: m.currency_id.round(m.amount_total) < 0).action_switch_invoice_into_refund_credit_note()

        return self.action_view_invoice(moves)

    @api.model
    def _prepare_down_payment_section_line(self, **optional_values):
        """
        Prepare the dict of values to create a new down payment section for a sales order line.

        :param optional_values: any parameter that should be added to the returned down payment section
        """
        context = {'lang': self.partner_id.lang}
        down_payments_section_line = {
            'display_type': 'line_section',
            'name': _('Down Payments'),
            'product_id': False,
            'product_uom_id': False,
            'quantity': 0,
            'discount': 0,
            'price_unit': 0,
            'account_id': False
        }
        del context
        if optional_values:
            down_payments_section_line.update(optional_values)
        return down_payments_section_line

    @api.onchange('partner_id')
    def onchange_partner_id_warning(self):
        res = super(PurchaseOrder, self).onchange_partner_id_warning()
        self._complete_advance_partner()
        return res

    def _complete_advance_partner(self):
        if self.partner_id:
            self.advance_check = self.partner_id.advance_check
            self.advance_payment_method = self.partner_id.advance_payment_method
            self.advance_amount = self.partner_id.advance_amount

    @api.onchange('advance_check')
    def _onchange_advance_check(self):
        for record in self:
            record._complete_advance_partner()

    @api.depends('order_line.price_total')
    def _amount_all(self):
        for order in self:
            amount_untaxed = amount_tax = 0.0
            amount_total_without_check = 0.0
            amount_tax_without_check = 0.0
            for line in order.order_line:
                line._compute_amount()
                if line.check_purchase or line.is_advance:
                    amount_untaxed += line.price_subtotal
                    amount_tax += line.price_tax
                amount_total_without_check += line.price_subtotal
                amount_tax_without_check += line.price_tax
            currency = order.currency_id or order.partner_id.property_purchase_currency_id or self.env.company.currency_id
            order.update({
                'amount_untaxed': currency.round(amount_untaxed),
                'amount_tax': currency.round(amount_tax),
                'amount_total': amount_untaxed + amount_tax,
                'amount_total_without_check': amount_total_without_check + amount_tax_without_check,
            })

    def view_requisition_request_id(self):
        self.ensure_one()
        if self.requisition_request_id:
            return {
                'name': 'Solicitud de aprobación : %s' % self.requisition_request_id.name,
                'type': 'ir.actions.act_window',
                'res_model': 'approval.request',
                'view_mode': 'form',
                'view_id': False,
                'views': [(self.env.ref('bpc_aliadas.approval_request_view_form_aliadas').id, 'form')],
                'res_id': self.requisition_request_id.id,
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message': _("No existe o no hay una orden de solitud de aprobación relacionada."),
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }

    def act_view_approval_request_purchase(self):
        requests_list = defaultdict(list)
        for record in self:
            if record.requisition_request_id:
                if record.requisition_request_id.request_status == 'pending':
                    requests_list[record.requisition_request_id].append(record)
                else:
                    raise ValidationError(_("Seleccione por favor solo ordenes con solicitudes en estado pendiente"))
            else:
                raise ValidationError(_("La orde de compra %s no tiene una solicitud de aprobación relacionada." % record.name))

        if requests_list:
            for request, purchase in requests_list.items():
                request.act_view_approval_request()

    def button_bidding_to_purchase(self):
        """PASAR PEDIDO DE FORMA FORZADA"""
        try:
            self.state = 'purchase'
            if self.force_picking:
                self._create_picking()
            self.force_purchase = True
        except Exception as e:
            raise ValidationError(_("Error generación picking : %s" % e))

    @api.model
    def _cron_purchase_order_approved_total(self):
        _logger.info("Ejecutando CRON - _cron_purchase_order_approved_total ")
        purchases = self.sudo().search([('state', '=', 'pending'),('send_mail_request','=',False)])
        for purchase in purchases:
            approved_count_ids = purchase.approval_request_ids.filtered(lambda l: l.request_status == 'approved')
            approved_count = len(approved_count_ids.ids)
            if len(purchase.approval_request_ids.ids) == approved_count and purchase.state == 'pending':
                template = self.env.ref('bpc_aliadas.mail_template_purchase_order_complete_approved', raise_if_not_found=False)
                try:
                    purchase.sudo().activity_schedule('bpc_aliadas.mail_activity_data_purchase_order_approved',
                                                  user_id=purchase.user_id.id,
                                                  note='Las solicitudes de la orden de compra %s han sido aprobadas' % purchase.name)
                    res = template.sudo().send_mail(purchase.id, notif_layout='mail.mail_notification_light', force_send=True, )
                    _logger.info("Resultado del envío a usuario %s es : %s " % (purchase.user_id.name, res))
                    purchase.sudo().write({'send_mail_request': True})
                except Exception as e:
                    _logger.warning("Error de envío a aprobador: %s " % e)

    # def action_rfq_send(self):
    #     '''
    #     This function opens a window to compose an email, with the edi purchase template message loaded by default
    #     '''
    #     self.ensure_one()
    #     ir_model_data = self.env['ir.model.data']
    #     try:
    #         if self.env.context.get('send_rfq', False):
    #             template_id = ir_model_data._xmlid_lookup('purchase.email_template_edi_purchase')[2]
    #         else:
    #             template_id = ir_model_data._xmlid_lookup('purchase.email_template_edi_purchase_done')[2]
    #     except ValueError:
    #         template_id = False
    #     try:
    #         compose_form_id = ir_model_data._xmlid_lookup('mail.email_compose_message_wizard_form')[2]
    #     except ValueError:
    #         compose_form_id = False
    #     ctx = dict(self.env.context or {})
    #     ctx.update({
    #         'default_model': 'purchase.order',
    #         'active_model': 'purchase.order',
    #         'active_id': self.ids[0],
    #         'default_res_id': self.ids[0],
    #         'default_use_template': bool(template_id),
    #         'default_template_id': template_id,
    #         'default_composition_mode': 'comment',
    #         'custom_layout': "mail.mail_notification_paynow",
    #         'force_email': True,
    #         'mark_rfq_as_sent': True,
    #     })
    #
    #     # In the case of a RFQ or a PO, we want the "View..." button in line with the state of the
    #     # object. Therefore, we pass the model description in the context, in the language in which
    #     # the template is rendered.
    #     lang = self.env.context.get('lang')
    #     if {'default_template_id', 'default_model', 'default_res_id'} <= ctx.keys():
    #         template = self.env['mail.template'].with_user(SUPERUSER_ID).browse(ctx['default_template_id'])
    #         if template:
    #             template.write({'email_to': self.partner_id.email_supplier})
    #             #template.email_to = self.partner_id.email_supplier
    #         if template and template.lang:
    #             lang = template._render_lang([ctx['default_res_id']])[ctx['default_res_id']]
    #
    #     self = self.with_context(lang=lang)
    #     if self.state in ['draft', 'sent']:
    #         ctx['model_description'] = _('Request for Quotation')
    #     else:
    #         ctx['model_description'] = _('Purchase Order')
    #
    #     return {
    #         'name': _('Compose Email'),
    #         'type': 'ir.actions.act_window',
    #         'view_mode': 'form',
    #         'res_model': 'mail.compose.message',
    #         'views': [(compose_form_id, 'form')],
    #         'view_id': compose_form_id,
    #         'target': 'new',
    #         'context': ctx,
    #     }
