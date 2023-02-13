# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, date
import logging
_logger = logging.getLogger(__name__)

STATE = [('done', 'Confirmado'), ('draft', 'Prospecto'), ('cancel', 'Rechazado'),('inactive','Inactivo')]


class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = 'res.partner'

    # company_type = fields.Selection(string='Tipo',
    #                                 selection=[('person', 'Contacto'), ('company', 'Compañía')],
    #                                 compute='_compute_company_type', inverse='_write_company_type')

    check_list_lines = fields.One2many('documents.check_list.lines', 'partner_id', domain=[('check_list_type','=','sale')])  #
    check_list_lines_supplier = fields.One2many('documents.check_list.lines', 'partner_id', domain=[('check_list_type','=','purchase')])  #

    check_retention = fields.Boolean(string='Retenciones')
    fiscal_customer_line_ids = fields.One2many('account.fiscal.position.line.customer', 'partner_id')
    fiscal_supplier_line_ids = fields.One2many('account.fiscal.position.line.purchase', 'partner_id')

    fiscal_lines = fields.Many2many('account.fiscal.position', 'fiscal_lines_sale_rel')
    fiscal_lines_supplier = fields.Many2many('account.fiscal.position', 'fiscal_lines_purchase_rel')

    advance_check = fields.Boolean(string='Aplica anticipo', help='Aplicación de anticipo solo a proveedores')  # P2 - Anticipo
    advance_payment_method = fields.Selection([('percentage', 'Porcentaje'), ('fixed', 'Monto fijo')], string='Tipo anticipo', default='percentage')  # P2 - Anticipo
    advance_amount = fields.Float(string='Monto anticipo')  # P2 - Anticipo

    now = fields.Date(compute='_compute_now')

    state = fields.Selection(STATE, string='Estado', default='done')
    is_customer = fields.Boolean(string='Es cliente')
    is_supplier = fields.Boolean(string='Es proveedor')
    email_supplier = fields.Char(string='Correo proveedor')

    commercial_ids = fields.One2many('res.partner.commercial', 'partner_id', string='Nombres comerciales')

    contract_count = fields.Integer(compute='_compute_contract_count')

    ex_number_purchase_order_exempt = fields.Char(string='N° Correlativo de la Orden de Compra Exenta')
    ex_number_register_constancy = fields.Char(string='N° Correlativo de la Constancia del Registro de Exonerados')
    ex_number_sag = fields.Char(string='N° Identificativo del Registro de la SAG')
    ex_number_diplomatic_card = fields.Char(string='N° Carnet Diplomático')

    user_payment_id = fields.Many2one('res.users', string='Responsable de cobro')

    pay_method_ids = fields.Many2many('payment.method', string='Métodos de pago')

    @api.constrains('vat')
    def _constraint_partner_vat(self):
        for record in self:
            if record.vat:
                vat = record.vat.strip()
                if len(vat) != 14:
                    raise ValidationError(_("El RTN debe contener 14 dígitos."))

    @api.constrains('advance_check', 'advance_payment_method', 'advance_amount')
    def _constraint_advance_amount(self):
        for record in self:
            if record.advance_check:
                if record.advance_payment_method == 'percentage' and record.advance_amount > 100:
                    raise ValidationError(_("Para aplicación de anticipo por porcentaje el monto a aplicar no debe ser mayor a 100"))

    @api.onchange('check_cai')
    def _onchange_check_cai(self):
        for record in self:
            if record.check_cai and not record.env.user.has_group('bpc_aliadas.group_aliadas_res_partner_cai_check'):
                raise ValidationError(_("Ud. no tiene permiso para activación de CAI. Comuníquese con el administrador del Sistema."))

    def get_check_list(self):
        for record in self:
            list = []
            check_list_actives = self.env['documents.check_list'].sudo().search([('state_active', '=', True),
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

    def get_check_list_purchase(self):
        for record in self:
            list = []
            check_list_actives = self.env['documents.check_list'].sudo().search([('state_active', '=', True),
                                                                                 ('type', '=', 'purchase'),
                                                                                 ('company_id', '=', record.env.company.id)])
            if check_list_actives:
                for item in check_list_actives:
                    find = record.check_list_lines_supplier.filtered(lambda l: l.check_list_id.id == item.id)
                    if not find:
                        list.append((
                            0, 0, {
                                'check_list_id': item.id,
                                'date_due': item.date_due
                            }
                        ))
                if list:
                    record.sudo().write({'check_list_lines_supplier': list})

            else:
                raise ValidationError(_("No hay checklist de documentos activos."))

    def _compute_now(self):
        for record in self:
            record.now = datetime.now().date()

    @api.onchange('state')
    def _onchange_state(self):
        for record in self:
            if record.state in ('cancel','inactive','draft'):
                record.active = False
            elif record.state == 'done':
                record._eval_sale_order_change(record.env.context)
                record.active = True

    def _eval_sale_order_change(self, context):
        _logger.info("Cambio de estado de cliente desde orden de venta")
        if 'default_model' in context and 'default_order_id' in context:
            if type(context['default_order_id']) == int and context['default_model'] == 'sale.order':
                order = self.env['sale.order'].sudo().browse(context['default_order_id'])
                if order:
                    _logger.info("Orden %s encontrada" % order.name)
                else:
                    _logger.info("Orden NO encontrada")
                if order and not order.accept_and_signed:
                    raise ValidationError(_("No puede confirmar el cliente si la orden no está - Aceptada y Firmada -"))
                elif order and order.accept_and_signed:
                    _logger.info("Orden firmada, continuará con el cambio de estado del cliente a CONFIRMADO.")

    @api.constrains('active')
    def _check_active(self):
        for record in self:
            if record.active:
                if not record.env.user.has_group("bpc_aliadas.group_aliadas_general_active_customer"):
                    raise ValidationError(_("Ud. no tiene permiso para activar un cliente."))
                else:
                    record.sudo().write({'state': 'done'})
            else:
                record.sudo().write({'state': 'draft'})


    def _compute_contract_count(self):
        for record in self:
            subs = self.env['sale.subscription'].sudo().search([('partner_id','=',record.id)])
            record.contract_count = len(subs.ids)

    def view_subscription_by_contract(self):
        self.ensure_one()
        if self.contract_count > 0:
            subs = self.env['sale.subscription'].sudo().search([('partner_id', 'in', self.ids)])
            if subs:
                return {
                    'type': 'ir.actions.act_window',
                    'name': _('Subscripciones / Contratos'),
                    'res_model': 'sale.subscription',
                    'view_type': 'list',
                    'view_mode': 'list',
                    'views': [[False, 'list'], [False, 'form']],
                    'domain': [('id', 'in', subs.ids)],
                }

            else:
                raise ValidationError(_("No se encontró subscripción"))
        else:
            raise ValidationError(_("No se encontró subscripciones relacionadas al contacto %s" % self.name))


class DocumentsChecklistLines(models.Model):
    _name = "documents.check_list.lines"
    _description = 'Check list documentos'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    partner_id = fields.Many2one('res.partner', string='Partner')
    now = fields.Date(compute='_compute_now')
    check_list_id = fields.Many2one('documents.check_list', string='Paso')
    check_list_type = fields.Selection(related='check_list_id.type')
    check_list_id_sequence = fields.Integer(related='check_list_id.sequence')
    check = fields.Boolean(string='Check')
    description = fields.Char(string='Observación')
    date_due = fields.Date(string='Fecha vencimiento')
    user_ids = fields.Many2many('res.users')

    def _compute_now(self):
        for record in self:
            record.now = datetime.now().date()

    def name_get(self):
        result = []
        for record in self:
            name = 'Doc. de %s' % record.partner_id.name
            result.append((record.id, name))

        return result



class AccountFiscalPosition(models.Model):
    _inherit = 'account.fiscal.position'

    #partner_id = fields.Many2one('res.partner', string='Partner')
    type = fields.Selection([('sale', 'Ventas'), ('purchase', 'Compras')], string='Usado para', default='sale')
    date_end = fields.Date(string='Fecha Venc.')

class AccountFiscalPositionLineCustomer(models.Model):
    _name = 'account.fiscal.position.line.customer'
    _description = 'Posición fiscal por partner'

    partner_id = fields.Many2one('res.partner', string='Partner')
    fiscal_id = fields.Many2one('account.fiscal.position', string='Posición fiscal', domain=[('type','=','sale')])
    fiscal_type = fields.Selection(related='fiscal_id.type', string='Tipo', readonly=False)
    date_end = fields.Date(string='Fecha Venc.')

class AccountFiscalPositionLinePurchase(models.Model):
    _name = 'account.fiscal.position.line.purchase'
    _description = 'Posición fiscal por partner'

    partner_id = fields.Many2one('res.partner', string='Partner')
    fiscal_id = fields.Many2one('account.fiscal.position', string='Posición fiscal', domain=[('type','=','purchase')])
    fiscal_type = fields.Selection(related='fiscal_id.type', string='Tipo', readonly=False)
    date_end = fields.Date(string='Fecha Venc.')



class PartnerNameCommercial(models.Model):
    _name = 'res.partner.commercial'
    _description = 'Nombre comercial de contactos'

    partner_id = fields.Many2one('res.partner', string='Partner')
    name = fields.Char(string='Nombre')

