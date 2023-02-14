# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, date
import json

class NoteTagBpc(models.Model):

    _name = "note.tag.bpc"
    _description = "Note Tag"

    name = fields.Char('Tag Name', required=True, translate=True)
    color = fields.Integer('Color Index')

    _sql_constraints = [
        ('name_uniq', 'unique (name)', "Tag name already exists !"),
    ]


class AccountMove(models.Model):
    _inherit = 'account.move'

    commercial_ids = fields.One2many(related='partner_id.commercial_ids')
    commercial_id = fields.Many2one('res.partner.commercial', string='Nombre comercial')
    subscription_contract_name = fields.Char(compute='_compute_subscription_contract_name', string='Contato N°', readonly=False, store=True)
    category_id = fields.Many2one('product.category', string='Plaza', compute='_compute_category_id')
    active = fields.Boolean(default=True, tracking=True, string='Activo')

    sale_id = fields.Many2one('sale.order', string='O. Centa')
    purchase_id = fields.Many2one('sale.order', string='O. Compra')

    def _get_payment_ref(self):
        invoice_payments_widget = self.invoice_payments_widget
        data = False
        if invoice_payments_widget:
            result = json.loads(invoice_payments_widget)
            pay = []
            if result:
                for content in result['content']:
                    pay.append(content['ref'])
                data = ','.join(pay)
        return data

    def _compute_subscription_contract_name(self):
        for record in self:
            contract_name = ''
            if not record.subscription_contract_name:
                if record.invoice_line_ids:
                    contract_name = record.invoice_line_ids[0].subscription_contract_name
            else:
                contract_name = record.subscription_contract_name
            record.subscription_contract_name = contract_name

    def view_subscription_by_contract(self):
        self.ensure_one()
        if self.subscription_contract_name:
            subcription_id = self.env['sale.subscription'].sudo().search([('contract_name','=',self.subscription_contract_name)])
            if subcription_id:
                return {
                    'name': _('Subscripción'),
                    'view_mode': 'form',
                    'res_model': 'sale.subscription',
                    'type': 'ir.actions.act_window',
                    'res_id': subcription_id.id
                }
            else:
                raise ValidationError(_("No se encontró subscripción para número de contrato %s " % self.subscription_contract_name))

    def _compute_category_id(self):
        for record in self:
            category_id = False
            if record.invoice_line_ids:
                invoice_line_id = record.invoice_line_ids[0]
                categ_id = invoice_line_id.product_id.categ_id

                def _square_parent(categ_id):
                    parent_id = False
                    if categ_id.parent_id:
                        parent_id = _square_parent(categ_id.parent_id)
                    else:
                        parent_id = categ_id

                    return parent_id

                if categ_id:
                    parent_id = _square_parent(categ_id)
                    category_id = parent_id

            record.category_id = category_id


    @api.model
    def _prepare_tax_lines_data_for_totals_from_object(self, object_lines, tax_results_function):
        """ Prepares data to be passed as tax_lines_data parameter of _get_tax_totals() from any
            object using taxes. This helper is intended for purchase.order and sale.order, as a common
            function centralizing their behavior.

            :param object_lines: A list of records corresponding to the sub-objects generating the tax totals
                                 (sale.order.line or purchase.order.line, for example)

            :param tax_results_function: A function to be called to get the results of the tax computation for a
                                         line in object_lines. It takes the object line as its only parameter
                                         and returns a dict in the same format as account.tax's compute_all
                                         (most probably after calling it with the right parameters).

            :return: A list of dict in the format described in _get_tax_totals's tax_lines_data's docstring.
        """
        tax_lines_data = []

        for line in object_lines:
            # if line._name == 'purchase.order.line' and not line.check_purchase:
            #     continue
            tax_results = tax_results_function(line)

            for tax_result in tax_results['taxes']:
                current_tax = self.env['account.tax'].browse(tax_result['id'])

                # Tax line
                tax_lines_data.append({
                    'line_key': f"tax_line_{line.id}_{tax_result['id']}",
                    'tax_amount': tax_result['amount'],
                    'tax': current_tax,
                })

                # Base for this tax line
                tax_lines_data.append({
                    'line_key': 'base_line_%s' % line.id,
                    'base_amount': tax_results['total_excluded'],
                    'tax': current_tax,
                })

                # Base for the taxes whose base is affected by this tax line
                if tax_result['tax_ids']:
                    affected_taxes = self.env['account.tax'].browse(tax_result['tax_ids'])
                    for affected_tax in affected_taxes:
                        tax_lines_data.append({
                            'line_key': 'affecting_base_line_%s_%s' % (line.id, tax_result['id']),
                            'base_amount': tax_result['amount'],
                            'tax': affected_tax,
                            'tax_affecting_base': current_tax,
                        })

        return tax_lines_data


