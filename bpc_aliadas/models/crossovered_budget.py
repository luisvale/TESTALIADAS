# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import date, timedelta, datetime
import json
import logging
_logger = logging.getLogger(__name__)

class CrossoveredBudget(models.Model):
    _inherit = "crossovered.budget"

    check_control = fields.Boolean(string='Check de control')

    @api.onchange('check_control')
    def _onchange_check_control(self):
        for record in self:
            crossovered_budget_line = record.crossovered_budget_line
            if crossovered_budget_line:
                crossovered_budget_line.sudo().write({'check_control': record.check_control})


class CrossoveredBudgetLines(models.Model):
    _inherit = "crossovered.budget.lines"

    check_control = fields.Boolean(string='Check')
    purchase_line_ids = fields.Many2many('purchase.order.line', string='Detalle orden de compra')
    purchase_ids = fields.Many2many('purchase.order', compute='_compute_purchase_ids', readonly=False, store=True)
    reserved_amount_total = fields.Monetary(string=u'Reservado total', help='Importe de total reservedo por ordenes de compra')
    # amount_used = fields.Float(help='Monto usado de la línea. Se tiene en cuenta esto, puesto que no siempre se tomará todo el monto, ya que ese monto'
    #                                 'puede estar incluido en 2 líneas de presupuestos diferentes')
    info = fields.Text(help='Información en JSON')
    reserved_amount = fields.Monetary(string=u'Reservado', compute='_compute_reserved_amount', help='Facturado - Reservado total')
    amount_pending = fields.Float(help='Monto pendiente a invertir (Previsto - Real - Reservado total)', compute='_compute_reserved_amount')

    def _find_analytic_line(self, line, create_date):
        if line:
            _logger.info("Presupuesto contable, evaluación ... ")
            date_planned = create_date - timedelta(hours=5)
            account_analytic_id = line.account_analytic_id
            account_id = line.account_id
            if account_analytic_id and account_id:
                crossovered_budget_lines = self.sudo().search([('analytic_account_id','=', account_analytic_id.id),
                                                               ('check_control','=',True),
                                                               ('general_budget_id', '!=', False)])
                if crossovered_budget_lines:
                    _logger.info("Se encontró presupuesto con la cuenta analítica %s " % account_analytic_id.name)

                _logger.info("Avaluando fechas y cuenta contable ... ")
                budget_line = crossovered_budget_lines.filtered(lambda l:l.date_from <= date_planned.date() and l.date_to >= date_planned.date()
                                                                and account_id.id in l.general_budget_id.account_ids.ids)
                if budget_line:
                    budget_aux = budget_line[0]
                    _logger.info("ALIADAS - %s Presupuesto(s) econtrados en esta fecha de recepción %s " % (len(budget_line.ids), date_planned.date()))

                    if budget_aux.currency_id != line.currency_id:
                        new_price_unit = line.currency_id._convert(line.price_unit, budget_aux.currency_id, budget_aux.company_id, date_planned or fields.Date.context_today(self))
                        price_unit = new_price_unit
                    else:
                        price_unit = line.price_unit
                    qty = line.product_qty
                    sub_total = qty * price_unit

                    total_budget = 0.0
                    for budget in budget_line:
                        amount = budget.planned_amount - budget.reserved_amount_total
                        total_budget += amount

                    _logger.info("ALIADAS - Total presupuestos: %s / Subtotal neta linea : %s " % (total_budget, sub_total))

                    #Si mi presupuesto no alcanza coloca el estado en EVALUACIÓN, sino no cambia el estado y continúa en DRAFT
                    if total_budget < sub_total and not line.order_id.force_budget:
                        _logger.info("ALIADAS - Pasó el limite de presupuesto, pasará a estado * evaluation *")
                        line.sudo().write({'limit_budget': True})
                        return True
                    else:
                        amount_line = sub_total
                        #Si pasa evaluamos el monto de la línea a qué o cuáles presupuesto se le asignará

                        #ordenamos por la cantidad mayor
                        budget_lines = self.search([('id','in',budget_line.ids)], order="amount_pending desc")

                        final_count = 0
                        for budget in budget_lines:
                            final_count += 1
                            print("Conteo : %s / Amount line: %s " % (final_count, amount_line))
                            if amount_line > 0:
                                #si mo monto pendiente a invertir es mayor al subtotal de la línea, entonces solo en ese se queda
                                if budget.amount_pending > amount_line:
                                    print("Monto pendiente : %s / Amount line: %s " % (budget.amount_pending, amount_line))
                                    budget.sudo().write({'reserved_amount_total': budget.reserved_amount_total + amount_line,
                                                         })
                                    budget.purchase_line_ids += line
                                    budget._add_budget_info(line, amount_line)
                                    break
                                else:
                                    #Evaluamos si llegamos a la línea final, de ser así, y no debe recorrer más el for
                                    #También evaluamos la asginación forzada del monto
                                    if final_count == len(budget_lines.ids) and line.order_id.force_budget:
                                        print("Reserva total : %s / Amount line: %s " % (budget.reserved_amount_total, amount_line))
                                        budget.sudo().write({'reserved_amount_total': budget.reserved_amount_total + amount_line})
                                        budget._add_budget_info(line, amount_line)
                                    else:
                                        to_used = budget.amount_pending
                                        budget.sudo().write({'reserved_amount_total': budget.reserved_amount_total + to_used})
                                        budget._add_budget_info(line, to_used)
                                        amount_line = amount_line - to_used
                                    budget.purchase_line_ids += line
            else:
                _logger.info("Analítica: %s " % account_analytic_id)
                _logger.info("Cuenta contable: %s " % account_id)

        return False

    def _add_budget_info(self, line, amount):
        info_budget = []
        if self.info not in ('', False):
            info_budget = json.loads(self.info)
        info_budget.append({
            'line_id': line.id,
            'amount': amount
        })
        self.info = json.dumps(info_budget)


    @api.depends('purchase_line_ids')
    def _compute_purchase_ids(self):
        for record in self:
            purchase_ids = self.env['purchase.order'].sudo()
            if record.purchase_line_ids:
                purchase_ids = record.purchase_line_ids.mapped('order_id')
            record.purchase_ids = purchase_ids

    @api.depends('purchase_ids','purchase_ids.state','purchase_ids.invoice_status','reserved_amount_total')
    def _compute_reserved_amount(self):
        for record in self:
            reserved_amount = 0.0
            reserved_amount_invoiced = 0.0
            amount_pending = 0.0
            if record.purchase_ids:
                purchase_invoiced_ids = record.purchase_ids.filtered(lambda p: p.invoice_status == 'invoiced')
                if purchase_invoiced_ids:
                    lines = record.purchase_line_ids.filtered(lambda l: l.order_id.id in purchase_invoiced_ids.ids)
                    for line in lines:
                        qty = line.product_qty
                        if record.currency_id != line.currency_id:
                            new_price_unit = line.currency_id._convert(line.price_unit, record.currency_id, record.company_id, line.date_planned.date() or fields.Date.context_today(self))
                            price_unit = new_price_unit
                        else:
                            price_unit = line.price_unit
                        sub_total = qty * price_unit
                        reserved_amount_invoiced += sub_total

            reserved_amount = record.reserved_amount_total - reserved_amount_invoiced
            record.reserved_amount = reserved_amount
            amount_pending = record.planned_amount - record.practical_amount - record.reserved_amount_total
            record.amount_pending = amount_pending

    def _update_reserved_amount_total(self):
        for record in self:
            lines = record.purchase_line_ids
            if record.info in ('', False):
                total_now = 0.0
                for line in lines:
                    if record.currency_id != line.currency_id:
                        new_price_unit = line.currency_id._convert(line.price_unit, record.currency_id, record.company_id, line.date_planned.date() or fields.Date.context_today(self))
                        total_now += line.product_qty * new_price_unit
                    else:
                        total_now += line.product_qty * line.price_unit
                #total_now = sum(line.product_qty * line.price_unit for line in lines)
                record.reserved_amount_total = total_now
            else:
                ids = lines.ids
                budget_info = json.loads(record.info)
                total = 0.0
                for info in budget_info:
                    if info['line_id'] in ids:
                        total += info['amount']
                record.reserved_amount_total = total
            record._compute_reserved_amount()