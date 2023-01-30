# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from datetime import date, datetime, timedelta
import traceback

from ast import literal_eval
from collections import Counter
from dateutil.relativedelta import relativedelta
from markupsafe import Markup
from uuid import uuid4

from odoo import api, fields, models, Command, _, SUPERUSER_ID
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from odoo.tools import format_date, is_html_empty, config
from odoo.tools.float_utils import float_is_zero

_logger = logging.getLogger(__name__)

PERIODS = {'daily': 'days', 'weekly': 'weeks', 'monthly': 'months', 'yearly': 'years'}

class SaleSubscription(models.Model):
    _name = 'sale.subscription'
    _inherit = 'sale.subscription'
    _order = 'id desc'

    contract_name = fields.Char(string='Contato N°', tracking=True, help='Número de contrato', copy=False, store=True)
    date_end = fields.Date(string='Fecha fin')
    check_pending_amount = fields.Boolean(compute='_compute_check_pending_amount')
    invoice_line_ids = fields.Many2many('account.move.line', compute='_compute_invoice_line_ids')

    local_ids = fields.Many2many('product.template', compute='_compute_local_ids', string='Locales')

    #Equipos de mant.
    maintenance_equipment_ids = fields.Many2many('maintenance.equipment', string='Equipos de mant.')

    # Aprobaciones
    approval_request_ids = fields.Many2many('approval.request', string='Solicitudes')
    approval_pending_count = fields.Float(compute='_compute_approval_required', copy=False, string='Pendientes')
    approval_approved_count = fields.Float(compute='_compute_approval_required', copy=False, string='Aprobadas')
    approval_cancel_count = fields.Float(compute='_compute_approval_required', copy=False, string='Canceladas/En espera')

    @api.model
    def _create_request(self, product_ids):

        if product_ids:
            category_id = self.env['approval.category'].sudo().search([('approval_type', '=', 'subs_new_product'), ('company_id', '=', self.company_id.id)], limit=1)

            approval_request = self.env['approval.request'].sudo()

            product_self = self.env['product.product'].sudo()

            if len(self.ids) > 0:

                approval_exist = approval_request.search([('category_id', '=', category_id.id),
                                                          ('subscription_id', '=', self.ids[0]),
                                                          ('request_status', 'not in', ['refused','cancel'])])
                if approval_exist and len(product_ids)>0:
                    for p in product_ids:
                        sw = 0
                        for app in approval_exist:
                            if app.product_ids:
                                if p.id in app.product_ids.ids:
                                    sw = 1
                                    break

                        if sw == 0:
                            product_self += p
                else:
                    product_self = product_ids

                if product_self:
                    _request = self.env['approval.request'].create({
                        'category_id': category_id.id,
                        'date_start': fields.Datetime.now(),
                        'date_end': fields.Datetime.now(),
                        'partner_id': self.env.user.partner_id.id,
                        'reference': self.name,
                        'origin': self.name,
                        'subscription_id': self.id,
                        'product_ids': [(6, 0, product_self.ids)]
                    })
                    if _request:
                        self.approval_request_ids += _request
            else:
                _logger.info("ALIADAS : Para envío de solicitud el ID de la subscripción aún no existe.")

        else:
            _logger.info("ALIADAS: No hay productos en subscripción")

    @api.constrains('recurring_invoice_line_ids')
    def _constraint_recurring_invoice_line_ids_custom(self):
        for record in self:
            if record.date_end:
                for line in record.recurring_invoice_line_ids:
                    if line.pickup_end:
                        days = (line.pickup_end - record.date_end).days
                        _logger.info("Cantidad de días : %s " % days)
                        if days > 0:
                            raise ValidationError(_("La línea que contiene el producto %s, posee una fecha de fin mayor a la de la subscripción" % line.product_id.name))

            lines_pending = record.recurring_invoice_line_ids.filtered(lambda l: l.approved_state=='new')
            if lines_pending:
                _logger.info("ALIADAS: Se encontraron %s lineas nuevas en la subscripción " % len(lines_pending.ids))
                product_ids = lines_pending.mapped('product_id')
                record._create_request(product_ids)


    def generate_contract_name(self):
        for record in self:
            _logger.info("Subscripción Name %s - ID %s " % (record.name, record.id))
            if not record.contract_name and record.stage_id.category == 'progress':
                seq_contract = self.env.ref('bpc_aliadas.sequence_subscription_contract_name')
                record.contract_name = seq_contract.next_by_id()
                _logger.info("Código de contrato generado %s " % record.contract_name)
            elif record.contract_name:
                _logger.info("Ya tiene un contrato")
            elif not record.stage_id.category == 'progress':
                _logger.info("Esta subscripción está en estado %s " % record.stage_id.category)


    def generate_contract_name_global_and_invoice(self):
        for record in self:
            record.generate_contract_name()
            if record.contract_name:
                line_ids = record.env['account.move.line'].sudo().search([('subscription_id','=',record.id)])
                if line_ids:
                    move_ids = line_ids.mapped('move_id')
                    for move in move_ids:
                        _logger.info("Generando códigos de contrato para facturas.")
                        move.sudo()._compute_subscription_contract_name()

                else:
                    _logger.info("No hay líneas para esta subscripción")

    def start_subscription(self):
        res = super(SaleSubscription, self).start_subscription()
        self.generate_contract_name()
        self._send_notification_to_team()
        return res

    def _send_notification_to_team(self):
        for record in self:
            if record.team_id:
                member_ids = record.team_id.member_ids
                try:
                    if member_ids:
                        partner_ids = member_ids.mapped('partner_id')
                        message = self.sudo().message_post(
                            body=f"Se creo la subscripción ! ({record.name})",
                            message_type='comment',
                            subtype_xmlid='mail.mt_comment',
                            partner_ids=partner_ids.ids
                        )
                        if message:
                            _logger.info("ALIADAS: Creación de mensaje exitosa!")

                except Exception as e:
                    _logger.info("Error de envío de notificación : %s " % e)



                #template_user = self.env.ref('bpc_aliadas.new_project_request_email_template')
                #
                # for member_id in member_ids:
                #     body_user = self._body_html_user(data, sol_patente, company_id)
                #     template_user.sudo().write({'body_html': body_user})
                #     template_user.sudo().send_mail(record.id, force_send=True)

    def _prepare_invoice_lines(self, fiscal_position):
        self.ensure_one()
        revenue_date_start = self.recurring_next_date
        revenue_date_stop = revenue_date_start + relativedelta(**{PERIODS[self.recurring_rule_type]: self.recurring_interval}) - relativedelta(days=1)
        lines = self.recurring_invoice_line_ids.filtered(lambda l: not float_is_zero(l.quantity, precision_rounding=l.product_id.uom_id.rounding))
        list_lines = []
        lines_locals = []
        for line in lines:
            # Si cumple con la validación, el producto no se deberá tomar en cuenta en el detalle de la factura.
            if self._filtered_local(line):
                lines_locals.append(line)
            else:
                list_lines.append((0, 0, self._prepare_invoice_line(line, fiscal_position, revenue_date_start, revenue_date_stop)))

        # Evluando añadir producto renta a la facturación
        if lines_locals:
            self._prepare_invoice_line_rental(list_lines, lines_locals, fiscal_position, revenue_date_start, revenue_date_stop)

        return list_lines

    def _prepare_invoice_lines_aliadas(self, fiscal_position, lines_group):
        self.ensure_one()
        revenue_date_start = self.recurring_next_date
        revenue_date_stop = revenue_date_start + relativedelta(**{PERIODS[self.recurring_rule_type]: self.recurring_interval}) - relativedelta(days=1)
        lines = lines_group
        list_lines = []
        lines_locals = []
        for line in lines:
            # Si cumple con la validación, el producto no se deberá tomar en cuenta en el detalle de la factura.
            if self._filtered_local(line):
                lines_locals.append(line)
            else:
                list_lines.append((0, 0, self._prepare_invoice_line(line, fiscal_position, revenue_date_start, revenue_date_stop)))

        # Evluando añadir producto renta a la facturación
        if lines_locals:
            self._prepare_invoice_line_rental(list_lines, lines_locals, fiscal_position, revenue_date_start, revenue_date_stop)

        return list_lines

    def _filtered_local(self, line):
        if line.product_id and line.product_id.rent_ok:
            return True
        else:
            return False

    def _next_date(self):
        subscription = self
        current_date = subscription.recurring_next_date
        next_date = subscription._get_recurring_next_date(subscription.recurring_rule_type, subscription.recurring_interval, current_date, subscription.recurring_invoice_day)
        return next_date

    def _prepare_invoice_line(self, line, fiscal_position, date_start=False, date_stop=False):
        values = super(SaleSubscription, self)._prepare_invoice_line(line, fiscal_position, date_start, date_stop)
        values = self._prepare_invoice_line_aliadas(values, line, False)
        return values

    def _prepare_invoice_line_rental(self, list_lines, lines_locals, fiscal_position, date_start=False, date_stop=False):
        line = lines_locals[0]
        company = self.env.company or line.analytic_account_id.company_id
        tax_ids = line.product_id.taxes_id.filtered(lambda t: t.company_id == company)
        if fiscal_position and tax_ids:
            tax_ids = self.env['account.fiscal.position'].browse(fiscal_position).map_tax(tax_ids)
        recurring_next_date = self.recurring_next_date
        amount_invoice = 0.0
        tags = []

        subs_line_ids = self.env['sale.subscription.line'].sudo()

        day_start_list = []
        if lines_locals:
            for local in lines_locals:
                if (local.pickup_start and local.pickup_end) or local.order_line_id:
                    lines, pending_invoiced = local._find_move_line(line.analytic_account_id, line.analytic_account_id.recurring_next_date)
                    pickup_start = False
                    if local.pickup_start:
                        pickup_start = local.pickup_start
                    elif local.order_line_id:
                        pickup_start = local.order_line_id.pickup_date

                    date_init = (pickup_start - timedelta(hours=6)) if not lines else lines.mapped('subscription_period_end')[0] + timedelta(days=1)
                    if type(date_init) == datetime:
                        date_init = date_init.date()

                    days = (recurring_next_date - date_init).days + 1  # El valor +1 indica que se cobrará desde el primer día
                    #price_subtotal = local.price_subtotal
                    total_subscription = local.total_subscription
                    # Precio a facturar
                    # Cuándo se debe dividir entre 30?
                    amount_invoice += (total_subscription / 30 * days)
                    name = 'SUBS_%s / %s - Días fact.: %s' % (self.ids[0], local.product_id.name, days)
                    tag = self.env['note.tag.bpc'].sudo().search([('name', '=', name)])
                    if tag:
                        tags.append((6, 0, tag.ids))
                    else:
                        tags.append((0, 0, {'name': name, 'color': 0}))
                    # tags.append((0, 0, {'name': name, 'color': 0}))
                    # date_init = recurring_next_date + timedelta(days=1)
                    local.sudo().write({'date_init': date_init, 'date_end': recurring_next_date})
                    day_start_list.append(date_init)
                    subs_line_ids += local

        product_rental_id = self.env.ref('bpc_aliadas.rental_product_bpc')

        values = {
            'name': product_rental_id.name,
            'subscription_id': line.analytic_account_id.id,
            'price_unit': amount_invoice,
            'quantity': 1,
            'product_uom_id': product_rental_id.uom_id.id,
            'product_id': product_rental_id.id,
            'tax_ids': [(6, 0, tax_ids.ids)],
            'subscription_start_date': date_start,
            'subscription_end_date': date_stop,
            'note_tag': tags,
        }

        if subs_line_ids:
            values.update({'subscription_line_ids': [(6, 0, subs_line_ids.ids)],
                           'subscription_id': line.analytic_account_id.id,
                           'subscription_period_start': min(day_start_list),
                           'subscription_period_end': recurring_next_date,
                           'subscription_next_invoiced': line.analytic_account_id._next_date()
                           })

        # only adding analytic_account_id and tag_ids if they exist in the sale.subscription.
        # if not, they will be computed used the analytic default rule
        if line.analytic_account_id.analytic_account_id.id:
            values.update({'analytic_account_id': line.analytic_account_id.analytic_account_id.id})
        if line.analytic_account_id.tag_ids.ids:
            values.update({'analytic_tag_ids': [(6, 0, line.analytic_account_id.tag_ids.ids)]})

        list_lines.append((0, 0, values))

    def _find_sale(self):
        sale = self.env['sale.order'].search([('order_line.subscription_id', 'in', self.ids)])
        return sale

    def _prepare_invoice_line_aliadas(self, values, line, manual=False):
        sale = self._find_sale()
        recurring_next_date = self.recurring_next_date
        if sale:
            if line.rental_type == 'm2':
                locals_ids = self.recurring_invoice_line_ids.filtered(lambda l:l.product_id.rent_ok)
                amount_invoice = 0.0
                tags = []
                if locals_ids:
                    for local in locals_ids:
                        pickup_date = local.pickup_start + timedelta(hours=6)
                        if type(pickup_date) == datetime:
                            pickup_date = pickup_date.date()
                        days = (recurring_next_date - pickup_date).days
                        total_subscription = local.total_subscription if line.currency_id == line.currency_external_id else local.amount_convert
                        # Precio a facturar
                        # Cuándo se debe dividir entre 30?
                        amount_invoice += (total_subscription / 30 * days)
                        name = 'SUBS_%s / Mant. %s - Días facturación: %s' % (self.ids[0], local.product_id.name, days)
                        tag = self.env['note.tag.bpc'].sudo().search([('name', '=', name)])
                        if tag:
                            tags.append((6, 0, tag.ids))
                        else:
                            tags.append((0, 0, {'name': name, 'color': 0}))

                    values['quantity'] = 1
                    values['price_unit'] = amount_invoice
                    values['note_tag'] = tags

            elif line.rental_type in ('consumption', 'consumption_min', 'consumption_fixed','rental_min', 'rental_percentage', 'rental_percentage_top'):
                #values['price_unit'] = line.price_subtotal if line.currency_id == line.currency_external_id else line.amount_convert
                #price_subtotal = line.price_subtotal if line.currency_id == line.currency_external_id else line.amount_convert
                total_subscription = line.total_subscription if line.currency_id == line.currency_external_id else line.amount_convert
                if line.pickup_start:
                    pickup_date = line.pickup_start + timedelta(hours=6)
                    days = (recurring_next_date - pickup_date.date()).days
                    total_subscription = (total_subscription / 30 * days)
                values['price_unit'] = total_subscription

            subscription = line.analytic_account_id
            values['subscription_line_ids'] = [(6, 0, line.ids)]
            values['subscription_id'] = subscription.id
            # values['date_init'] = False
            # values['date_end'] = False
            if manual:
                lines, pending_invoiced = line._find_move_line(subscription, line.date_end)
            else:
                lines, pending_invoiced = line._find_move_line(subscription, subscription.recurring_next_date)

            subscription_period_start = False
            subscription_period_end = False
            subscription_next_invoiced = False
            if lines and manual:
                if not pending_invoiced:
                    values['price_unit'] = line.pending_amount
                    values['subscription_is_pending'] = True
                    subscription_period_start = lines[0].subscription_period_start
                    subscription_period_end = lines[0].subscription_period_end
                    subscription_next_invoiced = lines[0].subscription_next_invoiced
                else:
                    return False

            elif lines and not manual:
                subscription_period_start = lines[0].subscription_period_end + timedelta(days=1)
                subscription_period_end = subscription.recurring_next_date
                subscription_next_invoiced = line.analytic_account_id._next_date()
                line.sudo().write({'date_init': line.pickup_start, 'date_end': subscription_period_end})

            else:
                subscription_period_start = subscription.date_start
                subscription_period_end = subscription.recurring_next_date
                subscription_next_invoiced = line.analytic_account_id._next_date()
                line.sudo().write({'date_init':  line.pickup_start, 'date_end': subscription_period_end})

            values['subscription_period_start'] = subscription_period_start
            values['subscription_period_end'] = subscription_period_end
            values['subscription_next_invoiced'] = subscription_next_invoiced
            values['subscription_line_consumption'] = line.amount_consumption
            values['subscription_line_sale'] = line.amount_sale
            values['subscription_line_percentage_sale'] = line.percentage_sale
            values['subscription_line_amount_min'] = line.amount_min
            values['subscription_line_amount_max'] = line.amount_max

        return values

    def generate_recurring_invoice(self):
        self._eval_fields()
        return super(SaleSubscription, self).generate_recurring_invoice()

    def _recurring_create_invoice(self, automatic=False, batch_size=20):
        if not self.env.company.invoice_subscription_group_by:
            return super(SaleSubscription, self)._recurring_create_invoice(automatic, batch_size)
        else:
            # Todo: En caso tenga activa la agrupación de facturas desde subcripción teniendo en cuenta el tipo de documento
            auto_commit = self.env.context.get('auto_commit', True)
            cr = self.env.cr
            invoices = self.env['account.move']
            current_date = datetime.today()  # cambio hecho por Jhonny
            # To avoid triggering the cron infinitely, we will add a temporary tag that will be removed by the last
            # call of the cron. The domain search will include the subscriptions without the tag.
            subscription_payment_exception_tag = self.env.ref('sale_subscription.subscription_payment_exception', raise_if_not_found=False)
            batch_tag = self.env.ref('sale_subscription.subscription_invalid_payment', raise_if_not_found=False)
            if automatic:
                if not subscription_payment_exception_tag:
                    subscription_payment_exception_tag = self.env['account.analytic.tag'].sudo().create({'name': 'Subscription Payment Exception', 'color': 4})
                    self.env['ir.model.data'].create({
                        'name': 'subscription_payment_exception',
                        'module': 'sale_subscription',
                        'res_id': subscription_payment_exception_tag.id,
                        'model': 'account.analytic.tag',
                        'noupdate': True
                    })
                if not batch_tag:
                    batch_tag = self.env['account.analytic.tag'].sudo().create(
                        {'name': 'Subscription Batch Invoicing', 'color': 4})
                    self.env['ir.model.data'].create({
                        'name': 'subscription_invalid_payment',
                        'module': 'sale_subscription',
                        'res_id': batch_tag.id,
                        'model': 'account.analytic.tag',
                        'noupdate': True
                    })
                if automatic and auto_commit:
                    cr.commit()

            # To avoid charging without updating the subscription, we will add a temporary tag that will be removed when the invoice is properly processed
            if len(self) > 0:
                subscriptions = self
                need_cron_trigger = False
            else:
                subscriptions = self.search(self._get_subscription_domain_for_invoicing(current_date, subscription_payment_exception_tag | batch_tag),
                                            limit=batch_size + 1)
                need_cron_trigger = len(subscriptions) > batch_size
                if need_cron_trigger:
                    subscriptions = subscriptions[:batch_size]
            if subscriptions:
                sub_data = subscriptions.read(fields=['id', 'company_id'])
                for company_id in set(data['company_id'][0] for data in sub_data):
                    sub_ids = [s['id'] for s in sub_data if s['company_id'][0] == company_id]
                    subs = self.with_company(company_id).with_context(company_id=company_id).browse(sub_ids)
                    # We tag the subscription. If something happen, it will prevent multiple payment attempt
                    Invoice = self.env['account.move'].with_context(move_type='out_invoice', company_id=company_id).with_company(company_id)
                    subs_order_lines = self.env['sale.order.line'].search([('subscription_id', 'in', sub_ids)])
                    for subscription in subs:
                        subscription = subscription[0]  # Trick to not prefetch other subscriptions, as the cache is currently invalidated at each iteration
                        sub_so = subs_order_lines.filtered(lambda ol: ol.subscription_id.id == subscription.id).order_id
                        sub_so_renewal = sub_so.filtered(lambda so: so.subscription_management == 'renew')
                        reference_so = max(sub_so_renewal, key=lambda so: so.date_order, default=False) or min(sub_so,
                                                                                                               key=lambda so: so.date_order,
                                                                                                               default=False)
                        invoice_ctx = {'lang': subscription.partner_id.lang}
                        if reference_so and reference_so.client_order_ref:
                            invoice_ctx['new_invoice_ref'] = reference_so.client_order_ref
                        if automatic and auto_commit:
                            cr.commit()

                        # if we reach the end date of the subscription then we close it and avoid to charge it
                        if automatic and subscription.date and subscription.date <= current_date:
                            subscription.set_close()
                            continue

                        # payment + invoice (only by cron)
                        if subscription.template_id.payment_mode == 'success_payment' and subscription.recurring_total and automatic:
                            subscription.with_context(mail_notrack=True).write({'tag_ids': [(4, subscription_payment_exception_tag.id)]})  # flag the sub in exception
                            if auto_commit:
                                cr.commit()
                            try:
                                payment_token = subscription.payment_token_id
                                tx = None
                                if payment_token:

                                    invoice_values = subscription.with_context(invoice_ctx)._prepare_invoice()
                                    new_invoice = Invoice.create(invoice_values)
                                    if subscription.analytic_account_id or subscription.tag_ids:
                                        useful_tags = subscription.tag_ids - subscription_payment_exception_tag - batch_tag
                                        for line in new_invoice.invoice_line_ids:
                                            if subscription.analytic_account_id:
                                                line.analytic_account_id = subscription.analytic_account_id
                                            if useful_tags:
                                                line.analytic_tag_ids = useful_tags
                                    new_invoice.message_post_with_view(
                                        'mail.message_origin_link',
                                        values={'self': new_invoice, 'origin': subscription},
                                        subtype_id=self.env.ref('mail.mt_note').id)
                                    tx = subscription._do_payment(payment_token, new_invoice)[0]
                                    # commit change as soon as we try the payment so we have a trace somewhere
                                    if auto_commit:
                                        cr.commit()
                                    if tx.renewal_allowed:
                                        subscription.with_context(mail_notrack=True).write({'tag_ids': [(3, subscription_payment_exception_tag.id)]})
                                        msg_body = _('Automatic payment succeeded. Payment reference: <a href=# data-oe-model=payment.transaction data-oe-id=%d>%s</a>; Amount: %s. Invoice <a href=# data-oe-model=account.move data-oe-id=%d>View Invoice</a>.') % (
                                        tx.id, tx.reference, tx.amount, new_invoice.id)
                                        subscription.message_post(body=msg_body)
                                        # success_payment
                                        if new_invoice.state != 'posted':
                                            new_invoice._post(False)
                                        subscription.send_success_mail(tx, new_invoice)
                                        if auto_commit:
                                            cr.commit()
                                    else:
                                        _logger.error('Fail to create recurring invoice for subscription %s', subscription.code)
                                        if auto_commit:
                                            cr.rollback()
                                        # Check that the invoice still exists before unlinking. It might already have been deleted by `reconcile_pending_transaction`.
                                        new_invoice.exists().unlink()
                                if tx is None or not tx.renewal_allowed:
                                    amount = subscription.recurring_total
                                    auto_close_limit = subscription.template_id.auto_close_limit or 15
                                    date_close = (
                                            subscription.recurring_next_date +
                                            relativedelta(days=auto_close_limit)
                                    )
                                    close_subscription = current_date >= date_close
                                    email_context = self.env.context.copy()
                                    email_context.update({
                                        'payment_token': subscription.payment_token_id and subscription.payment_token_id.name,
                                        'renewed': False,
                                        'total_amount': amount,
                                        'email_to': subscription.partner_id.email,
                                        'code': subscription.code,
                                        'currency': subscription.pricelist_id.currency_id.name,
                                        'date_end': subscription.date,
                                        'date_close': date_close,
                                        'auto_close_limit': auto_close_limit
                                    })
                                    if close_subscription:
                                        template = self.env.ref('sale_subscription.email_payment_close')
                                        template.with_context(email_context).send_mail(subscription.id)
                                        _logger.debug("Sending Subscription Closure Mail to %s for subscription %s and closing subscription", subscription.partner_id.email, subscription.id)
                                        msg_body = _('Automatic payment failed after multiple attempts. Subscription closed automatically.')
                                        subscription.message_post(body=msg_body)
                                        subscription.set_close()
                                        # remove the exception flag as we are done with this sub
                                        subscription.with_context(mail_notrack=True).write({'tag_ids': [(3, subscription_payment_exception_tag.id)]})
                                    else:
                                        subscription.write({'tag_ids': [Command.link(batch_tag.id)]})
                                        template = self.env.ref('sale_subscription.email_payment_reminder')
                                        msg_body = _('Automatic payment failed. Subscription set to "To Renew".')
                                        if (datetime.date.today() - subscription.recurring_next_date).days in [0, 3, 7, 14]:
                                            template.with_context(email_context).send_mail(subscription.id)
                                            _logger.debug("Sending Payment Failure Mail to %s for subscription %s and setting subscription to pending", subscription.partner_id.email, subscription.id)
                                            msg_body += _(' E-mail sent to customer.')
                                        subscription.message_post(body=msg_body)
                                        subscription.set_to_renew()
                                        # remove the flag as we are done with this sub
                                        subscription.with_context(mail_notrack=True).write({'tag_ids': [(3, subscription_payment_exception_tag.id)]})
                                if auto_commit:
                                    cr.commit()
                            except Exception:
                                if auto_commit:
                                    cr.rollback()
                                # we assume that the payment is run only once a day
                                traceback_message = traceback.format_exc()
                                _logger.error(traceback_message)
                                last_tx = self.env['payment.transaction'].search([('reference', 'like', 'SUBSCRIPTION-%s-%s' % (subscription.id, datetime.date.today().strftime('%y%m%d')))], limit=1)
                                error_message = "Error during renewal of subscription %s (%s)" % (subscription.code, 'Payment recorded: %s' % last_tx.reference if last_tx and last_tx.state == 'done' else 'No payment recorded.')
                                _logger.error(error_message)

                        # invoice only
                        elif subscription.template_id.payment_mode in ['draft_invoice', 'manual', 'validate_send']:
                            try:
                                # We don't allow to create invoice past the end date of the contract.
                                # The subscription must be renewed in that case
                                if subscription.date and subscription.recurring_next_date >= subscription.date:
                                    return
                                else:
                                    lines_invoice = subscription._lines_to_process()
                                    if not lines_invoice:
                                        continue
                                    for lines in lines_invoice:
                                        invoice_values = subscription.with_context(invoice_ctx)._prepare_invoice_aliadas(lines['lines'], lines['document_type_sale_id'], lines['currency_id'])
                                        if invoice_values:
                                            new_invoice = Invoice.create(invoice_values)
                                            if subscription.analytic_account_id or subscription.tag_ids:
                                                for line in new_invoice.invoice_line_ids:
                                                    if subscription.analytic_account_id:
                                                        line.analytic_account_id = subscription.analytic_account_id
                                                    if subscription.tag_ids:
                                                        line.analytic_tag_ids = subscription.tag_ids
                                            new_invoice.message_post_with_view(
                                                'mail.message_origin_link',
                                                values={'self': new_invoice, 'origin': subscription},
                                                subtype_id=self.env.ref('mail.mt_note').id)
                                            invoices += new_invoice
                                            # When `recurring_next_date` is updated by cron or by `Generate Invoice` action button,
                                            # write() will skip resetting `recurring_invoice_day` value based on this context value
                                            if subscription.template_id.payment_mode == 'validate_send':
                                                new_invoice.action_post()
                                    subscription.with_context(skip_update_recurring_invoice_day=True).increment_period()
                                    if automatic and auto_commit:
                                        cr.commit()
                            except Exception:
                                if automatic and auto_commit:
                                    cr.rollback()
                                    _logger.exception('Fail to create recurring invoice for subscription %s', subscription.code)
                                else:
                                    raise

            # Retrieve the invoice to send mails.
            self._cr.execute('''
                SELECT
                    DISTINCT aml.move_id,
                    move.date
                FROM account_move_line aml
                JOIN sale_subscription subscr ON subscr.id = aml.subscription_id
                JOIN sale_subscription_template subscr_tpl ON subscr_tpl.id = subscr.template_id
                JOIN account_move move ON move.id = aml.move_id
                WHERE move.state = 'posted'
                    AND move.is_move_sent IS FALSE
                    AND subscr_tpl.payment_mode = 'validate_send'
                ORDER BY move.date DESC
            ''')
            invoice_to_send_ids = [row[0] for row in self._cr.fetchall()]

            invoices_to_send = self.env['account.move'].browse(invoice_to_send_ids)
            for invoice in invoices_to_send:
                if invoice._is_ready_to_be_sent():
                    subscription = invoice.line_ids.subscription_id[:1]  # Only select one in case of multiple subscriptions on the invoice
                    subscription.validate_and_send_invoice(invoice)

            # There is still some subscriptions to process. Then, make sure the CRON will be triggered again asap.
            if need_cron_trigger:
                if config['test_enable'] or config['test_file']:
                    # Test environnement: we launch the next iteration in the same thread
                    self.env['sale.subscription']._recurring_create_invoice(automatic, batch_size)
                else:
                    self.env.ref('sale_subscription.account_analytic_cron_for_invoice')._trigger()

            # If this is the last call of the cron and if the invalid_payment_tag is defined, we can remove the tag used
            # mark the payment failed subscriptions.
            if not need_cron_trigger and batch_tag:
                failing_subscriptions = self.search([('tag_ids', 'in', batch_tag.ids)])
                failing_subscriptions.write({'tag_ids': [Command.unlink(batch_tag.id)]})

            return invoices

    def _eval_fields(self):
        for record in self:
            recurring_invoice_line_ids = record.recurring_invoice_line_ids
            for line in recurring_invoice_line_ids:
                rental_type = line.rental_type
                name = line.product_id.name
                # if rental_type in ('consumption', 'consumption_min', 'consumption_fixed'):
                #     if not line.amount_consumption or line.amount_consumption == 0.0:
                #         raise ValidationError(_("Asegúrese de tener un valor ingresado en la columna CONSUMO para el producto %s " % name))
                # elif rental_type in ('rental_min', 'rental_percentage', 'rental_percentage_top'):
                if rental_type in ('rental_min', 'rental_percentage', 'rental_percentage_top', 'consumption', 'consumption_min', 'consumption_fixed'):
                    if rental_type == 'rental_percentage':
                        if not line.percentage_sale or line.percentage_sale == 0.0:
                            raise ValidationError(_("Asegúrese de tener un valor ingresado en la columna PORCENTAJE SOBRE VENTAS para el producto %s " % name))
                        # if not line.amount_sale or line.amount_sale == 0.0:
                        #     raise ValidationError(_("Asegúrese de tener un valor ingresado en la columna VENTAS para el producto %s " % name))
                    else:
                        if (not line.amount_min or line.amount_min == 0.0) and (not line.amount_max or line.amount_max == 0.0):
                            raise ValidationError(_("Asegúrese de tener un valor ingresado en la columna MÍNIMO o MÁXIMO para el producto %s " % name))

            find_document = recurring_invoice_line_ids.filtered(lambda l: not l.document_type_sale_id)
            if find_document:
                raise ValidationError(_("Asegúrese de establecer un tipo de documento para el producto %s " % name))

    def _prepare_invoice_aliadas(self, lines, document_type_sale_id, currency_id):
        """
        Note that the company of the environment will be the one for which the invoice will be created.

        :returns: account.move create values
        :rtype: dict
        """
        invoice = self._prepare_invoice_data()
        invoice['currency_id'] = currency_id
        invoice['document_type_sale_id'] = document_type_sale_id
        invoice['check_cai'] = True
        invoice['invoice_line_ids'] = self._prepare_invoice_lines_aliadas(invoice['fiscal_position_id'], lines)
        sale = self._find_sale()
        if sale and sale.commercial_id:
            invoice['commercial_id'] = sale.commercial_id.id
        return invoice

    def _prepare_invoice_aliadas_manual(self, lines, document_type_sale_id, currency_id):

        manual_lines = lines.filtered(lambda l: l.pending_amount > 0.0)
        if not manual_lines:
            return False
        invoice = self._prepare_invoice_data()
        invoice['currency_id'] = currency_id
        invoice['document_type_sale_id'] = document_type_sale_id
        list_lines = []
        for line in manual_lines:
            if not self._filtered_local(line):
                values = self._prepare_invoice_line(line, False, line.date_init, line.date_end)
                values = self._prepare_invoice_line_aliadas(values, line, True)
                if values:
                    list_lines.append((0, 0, values))
        if not list_lines:
            return False
        invoice['invoice_line_ids'] = list_lines
        return invoice

    @api.depends('recurring_invoice_line_ids', 'recurring_invoice_line_ids.pending_amount')
    def _compute_check_pending_amount(self):
        for record in self:
            lines = record.recurring_invoice_line_ids.filtered(lambda r: r.pending_amount > 0.0)
            record.check_pending_amount = True if len(lines.ids) > 0 else False

    def _lines_to_process(self):
        lines_invoice = []
        document_type_sale_id = False
        currency_id = False
        self._cr.execute('''
                            select document_type_sale_id,
                            (case when currency_external_id != currency_id then currency_external_id else currency_id end) as id_currency
                             from sale_subscription_line 
                            where analytic_account_id = %s
                            --group by document_type_sale_id, currency_external_id, currency_id
                            group by document_type_sale_id, (case when currency_external_id != currency_id then currency_external_id else currency_id end) 
                        ''' % self.id)

        query_res = self._cr.fetchall()
        ril_all = self.recurring_invoice_line_ids
        ril_local = self.recurring_invoice_line_ids._filtered_local_by_line()
        ril_not_local = ril_all - ril_local
        lines_list = []
        if ril_local:
            lines_list.append(ril_local)
        if ril_not_local:
            lines_list.append(ril_not_local)
        #lines_list = [ril_local, ril_not_local]
        if query_res:
            for res in query_res:
                document_type_sale_id = res[0]
                currency_id = res[1]
                for ril in lines_list:
                    lines = ril.filtered(lambda l: l.document_type_sale_id.id == document_type_sale_id and
                                                   (l.currency_external_id.id == currency_id if l.currency_external_id else l.currency_id.id == currency_id))
                    if lines:
                        lines_invoice.append({'lines': lines, 'document_type_sale_id': document_type_sale_id, 'currency_id': currency_id})
        return lines_invoice

    def manual_invoice(self):
        for subscription in self:
            if subscription.check_pending_amount:
                lines_invoice = subscription._lines_to_process()
                if not lines_invoice:
                    _logger.info("Subscription (manual_invoice) - no se encontraron líneas a facturar")
                    continue
                for lines in lines_invoice:
                    subs_order_lines = self.env['sale.order.line'].search([('subscription_id', 'in', subscription.ids)])
                    Invoice = self.env['account.move'].with_context(move_type='out_invoice', company_id=subscription.company_id).with_company(subscription.company_id)
                    sub_so = subs_order_lines.filtered(lambda ol: ol.subscription_id.id == subscription.id).order_id
                    sub_so_renewal = sub_so.filtered(lambda so: so.subscription_management == 'renew')
                    reference_so = max(sub_so_renewal, key=lambda so: so.date_order, default=False) or min(sub_so,
                                                                                                           key=lambda so: so.date_order,
                                                                                                           default=False)
                    invoice_ctx = {'lang': subscription.partner_id.lang}
                    if reference_so and reference_so.client_order_ref:
                        invoice_ctx['new_invoice_ref'] = reference_so.client_order_ref

                    invoice_values = subscription.with_context(invoice_ctx)._prepare_invoice_aliadas_manual(lines['lines'], lines['document_type_sale_id'], lines['currency_id'])
                    if invoice_values:
                        new_invoice = Invoice.create(invoice_values)
                        if subscription.analytic_account_id or subscription.tag_ids:
                            for line in new_invoice.invoice_line_ids:
                                if subscription.analytic_account_id:
                                    line.analytic_account_id = subscription.analytic_account_id
                                if subscription.tag_ids:
                                    line.analytic_tag_ids = subscription.tag_ids
                        new_invoice.message_post_with_view(
                            'mail.message_origin_link',
                            values={'self': new_invoice, 'origin': subscription},
                            subtype_id=self.env.ref('mail.mt_note').id)

                        if new_invoice:
                            _logger.info("ALIADAS: Factura pendiente con ID %s creada de forma manual desde subscripción" % new_invoice.id)
                            # return {
                            #     'type': 'ir.actions.client',
                            #     'tag': 'display_notification',
                            #     'params': {
                            #         'type': 'success',
                            #         'title': 'Bien!',
                            #         'message': _("Comprobante creado correctamente..."),
                            #         'next': {'type': 'ir.actions.act_window_close'},
                            #     }
                            # }

            # recurring_invoice_line_ids = subscription.recurring_invoice_line_ids
            # recurring_invoice_line_ids.sudo().write({''})

    def partial_invoice_line_all(self, sale_order, option_line, refund=False, date_from=False):
        """ Add an invoice line on the sales order for the specified option and add a discount
        to take the partial recurring period into account """
        order_line_obj = self.env['sale.order.line']
        ratio, message, period_msg = self.with_context(lang=sale_order.partner_id.lang)._partial_recurring_invoice_ratio(date_from=date_from)
        if message != "":
            sale_order.message_post(body=message)
        values = {
            'order_id': sale_order.id,
            'product_id': option_line.product_id.id,
            'subscription_id': self.id,
            'product_uom_qty': option_line.quantity,
            'product_uom': option_line.uom_id.id,
            'discount': option_line.discount,
            'price_unit': option_line.price_unit,
            'name': order_line_obj.with_context(lang=sale_order.partner_id.lang).get_sale_order_line_multiline_description_sale(
                option_line.product_id.with_context(lang=sale_order.partner_id.lang)) + '\n' + period_msg,
            'pickup_date': option_line.pickup_date,
            'return_date': option_line.return_date,
        }
        return order_line_obj.create(values)

    def action_subscription_all_wizard(self):
        subcription_ids = self.env['sale.subscription'].browse(self._context.get('active_ids'))
        if subcription_ids:
            view = self.env.ref('bpc_aliadas.wizard_all_form_view')
            return {
                'name': 'Ventas adicionales / %s subscripciones seleccionadas' % (len(subcription_ids.ids)),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'sale.subscription.all.wizard',
                'views': [(view.id, 'form')],
                'view_id': view.id,
                'target': 'new',
                'context': dict(default_subscription_ids=subcription_ids.ids),
            }

    def _compute_invoice_line_ids(self):
        for record in self:
            lines = self.env['account.move.line'].sudo().search([('subscription_id', '=', record.ids[0])])
            record.invoice_line_ids = lines

    def _compute_local_ids(self):
        for record in self:
            templates = self.env['product.template'].sudo()
            for line in record.recurring_invoice_line_ids:
                product_rental_id = self.env.ref('bpc_aliadas.rental_product_bpc')
                if line.product_id.rent_ok and line.product_id.id != product_rental_id.id:
                    templates += line.product_id.product_tmpl_id
            record.local_ids = templates

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
                    pass
                    #record.state = 'approved'
            record.approval_pending_count = pending_count
            record.approval_approved_count = approved_count
            record.approval_cancel_count = cancel_count

    @api.onchange('maintenance_equipment_ids')
    def _onchange_maintenance_equipment_ids(self):
        for record in self:
            if record.maintenance_equipment_ids and record.recurring_invoice_line_ids:
                lines = record.recurring_invoice_line_ids.filtered(lambda l: l.rental_type == 'tonnage')
                for line in lines:
                    price_unit = sum(e.tonnage_id.price if e.tonnage_id else 0.0 for e in record.maintenance_equipment_ids)
                    line.sudo().write({'price_unit': price_unit})
