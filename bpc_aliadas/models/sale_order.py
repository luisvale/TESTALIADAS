# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import timedelta, date, datetime
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged, Form
from odoo.tools import is_html_empty
from .. import sale
import logging
_logger = logging.getLogger(__name__)

STATE_PROSPECT = [('done', 'Confirmado'), ('draft', 'Prospecto'), ('cancel', 'Rechazado'), ('inactive','Inactivo')]

class SaleOrder(models.Model):
    _inherit = "sale.order"

    partner_prospect_id = fields.Many2one('res.partner',domain=[('active','=',False),('state','=','draft')], string='Prospecto cliente')
    partner_prospect_state = fields.Selection(STATE_PROSPECT, compute='_compute_partner_prospect_state', string='Estado cliente')

    commercial_ids = fields.One2many(related='partner_id.commercial_ids')
    commercial_id = fields.Many2one('res.partner.commercial', string='Nombre comercial')

    def _default_payment_term(self):
        return self.env.ref('account.account_payment_term_immediate')

    check_list_lines = fields.One2many('sale.order.check_list.lines', 'sale_id')
    perm_can_project = fields.Boolean(help='Se debe crear proyecto?', compute='_compute_perm_can_project', store=True, copy=False, readonly=False)
    create_project_automatic_manual = fields.Boolean(compute='_compute_create_project_automatic_manual', tracking=True, store=True, string='Creación de proyecto automáticamente')
    not_project = fields.Boolean(related='team_id.not_project', readonly=False)
    hide_columns_mim_max = fields.Boolean(related='team_id.hide_columns_mim_max', readonly=False)
    authorization_payment_term = fields.Boolean(related='team_id.authorization_payment_term', readonly=False)
    invoice_payment = fields.Boolean(help='Al menos una factura cancelada', compute='_compute_invoice_payment', store=True)
    payment_term_id = fields.Many2one('account.payment.term', string='Plazo de pago', check_company=True,  # Unrequired company
                                      domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]", default=_default_payment_term,
                                      required=True)

    state = fields.Selection([
        ('draft', 'Quotation'),
        ('pending', 'Esperando aprobación'),  # custom
        ('approved', 'Aprobada'),  # custom
        ('compliance', 'Cumplimiento'),  # custom
        ('sent', 'Quotation Sent'),
        ('sale', 'Sales Order'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled'),
    ], string='Status', readonly=True, copy=False, index=True, tracking=3, default='draft')

    rental_status = fields.Selection([
        ('draft', 'Quotation'),
        ('pending', 'Esperando aprobación'),
        ('approved', 'Aprobada'),
        ('compliance', 'Cumplimiento'),  # custom
        ('sent', 'Quotation Sent'),
        ('pickup', 'Confirmed'),
        ('return', 'Picked-up'),
        ('returned', 'Returned'),
        ('cancel', 'Cancelled'),
    ], string="Rental Status", compute='_compute_rental_status', store=True)

    purchase_ids = fields.Many2many('purchase.order', string='Ordenes de compra', copy=False)
    margin_sale = fields.Monetary(string='Margen', compute='_compute_margin_sale', copy=False)
    margin_test = fields.Float(help='Margen a evaluar', copy=False, compute='_compute_margin_sale')

    approval_request_ids = fields.Many2many('approval.request', string='Solicitudes', copy=False)
    approval_pending_count = fields.Float(compute='_compute_approval_required', copy=False, string='Pendientes')
    approval_approved_count = fields.Float(compute='_compute_approval_required', copy=False, string='Aprobadas')
    approval_cancel_count = fields.Float(compute='_compute_approval_required', copy=False, string='Canceladas/En espera')
    approval_force = fields.Boolean()

    currency_rate = fields.Float(compute='_compute_currency_rate', store=True) #TIPO DE CAMBIO

    accept_and_signed = fields.Boolean(string='Aceptada y Firmada')

    # @api.onchange('partner_prospect_id')
    # def _onchange_partner_prospect_id(self):
    #     for record in self:
    #         if record.partner_prospect_id:
    #             record.partner_id = record.partner_prospect_id

    # @api.model
    # def create(self, vals):
    #     res = super(SaleOrder, self).create(vals)
    #     a=1
    #     return res

    @api.constrains('state')
    def _constraint_order_state(self):
        for record in self:
            if record.state == 'sale' and record.partner_id.state != 'done':
                raise ValidationError(_("Para pasar a orden de venta asegúrese que el cliente tenga el estado CONFIRMADO."))


    @api.depends('partner_prospect_id','partner_prospect_id.state','partner_prospect_id.active')
    def _compute_partner_prospect_state(self):
        for record in self:
            if record.partner_prospect_id:
                record.partner_prospect_state = record.partner_prospect_id.state
                record.partner_id = record.partner_prospect_id
            elif record.partner_id:
                record.partner_prospect_state = record.partner_id.state
            else:
                record.partner_prospect_state = 'done'

    @api.depends('currency_id')
    def _compute_currency_rate(self):
        for record in self:
            currency_rate = 1
            if record.company_id.currency_id != record.currency_id:
                currency_rate = record.currency_id._convert(1, record.company_id.currency_id, record.company_id, record.date_order.date() or datetime.now().date())
            record.currency_rate = currency_rate

    def get_check_list(self):
        for record in self:
            list = []
            check_list_actives = self.env['sale.order.check_list'].sudo().search([('state_active', '=', True), ('company_id', '=', record.company_id.id)])
            if check_list_actives:
                for item in check_list_actives:
                    list.append((
                        0, 0, {
                            'check_list_id': item.id
                        }
                    ))
                if list:
                    record.sudo().write({'check_list_lines': list})

            else:
                raise ValidationError(_("No hay pasos en el checklist activos."))

    def update_prices(self):
        if not self.payment_term_id:
            raise ValidationError(_("Asigne por favor algún plazo de pago"))
        super().update_prices()
        # Apply correct rental prices with respect to pricelist
        for sol in self.order_line.filtered(lambda line: line.is_rental):
            pricing = sol.product_id._get_best_pricing_rule(
                pickup_date=sol.pickup_date,
                return_date=sol.return_date,
                pricelist=self.pricelist_id,
                currency=self.currency_id,
                company=self.company_id
            )
            if not pricing:
                if sol.company_id.check_pricelist:
                    price_unit = sol.product_id._get_tax_included_unit_price(
                        sol.company_id or sol.order_id.company_id,
                        sol.order_id.currency_id,
                        sol.order_id.date_order,
                        'sale',
                        fiscal_position=sol.order_id.fiscal_position_id,
                        product_price_unit=sol._get_display_price(sol.product_id),
                        product_currency=sol.order_id.currency_id
                    )
                    sol.price_unit = price_unit
                    sol.price_min = price_unit
                else:
                    sol.price_unit = sol.product_id.lst_price
                    sol.price_min = sol.product_id.lst_price
                continue
            duration_dict = self.env['rental.pricing']._compute_duration_vals(sol.pickup_date, sol.return_date)
            price = pricing._compute_price(duration_dict[pricing.unit], pricing.unit)

            if pricing.currency_id != self.currency_id:
                price = pricing.currency_id._convert(
                    from_amount=price,
                    to_currency=self.currency_id,
                    company=self.company_id,
                    date=date.today(),
                )
            sol.price_unit = price
            sol.price_min = price
            sol.discount = 0

        for line in self._get_update_prices_lines():
            line.price_min = line.price_unit

    # TODO: ********** CREACIÓN DE PROYECTOS ************+

    def create_project_manual(self):
        for order in self:
            order.order_line.sudo().with_company(order.company_id)._timesheet_service_generation()

    @api.depends('invoice_payment')
    def _compute_create_project_automatic_manual(self):
        for record in self:
            create_project_automatic_manual = False
            if record.invoice_payment:
                record.create_project_manual()
            record.create_project_automatic_manual = create_project_automatic_manual

    @api.model
    def create(self, vals_list):
        res = super(SaleOrder, self).create(vals_list)
        self.test_exist_request_payment_term(vals_list, 'create', res)
        self._change_stage_opportunity(vals_list)
        return res

    def write(self, vals):
        res = super(SaleOrder, self).write(vals)
        self.test_exist_request_payment_term(vals, 'write', res)
        self._state_lead(vals)
        return res

    def test_exist_request_payment_term(self, vals, process, res):
        """Evaluamos si existe ya algún envió de solicitud para aprobación por cambio en térmminos de pago.
        Hay que tener en cuenta que si ya se envió no debe volver a hacerlo y tampoco debe permitir cambiar esto.
        Lo que ayudará es que al cambiar pasará automáticamente a estado de esperando aprobación"""

        account_payment_term_immediate_id = self.env.ref('account.account_payment_term_immediate').id

        def _find(payment_term_id, record):
            _logger.info("ALIADAS: Revisando plazo de pago ...Se necesita ID %s - Usuario ingresa ID %s" % (account_payment_term_immediate_id, payment_term_id))
            if payment_term_id != account_payment_term_immediate_id:
                # Evaluar si existe alguna solcitud
                send = False
                _request = record._exist_request_by_category(category='payment_term')
                if not _request:
                    send = True
                if send:
                    _logger.info("ALIADAS: Se enviará solicitud por categoría término de pago")
                    # En caso no haya ninguna solictud por la categoría término de pago, entonces enviamos solicitud
                    record._create_request('payment_term')
                    record.sudo().write({'state': 'pending'})

                else:
                    _logger.info("ALIADAS: NO Se enviará solicitud por categoría término de pago, hay alguna ")
        if process == 'write':
            if self.authorization_payment_term:
                _logger.info("ALIADAS: Write - Solicitando autorización para cambio de plazos de pago")
                if 'payment_term_id' in vals:
                    _find(vals['payment_term_id'], self)
            else:
                _logger.info("ALIADAS: Write - No se requiere autorización para cambio de plazos de pago")

        elif process == 'create':
            if res.authorization_payment_term:
                _logger.info("ALIADAS: Create - Solicitando autorización para cambio de plazos de pago")
                _find(res.payment_term_id.id, res)
            else:
                _logger.info("ALIADAS: Create - No se requiere autorización para cambio de plazos de pago")

    @api.depends('invoice_payment', 'not_project')
    def _compute_perm_can_project(self):
        for record in self:
            record.perm_can_project = True if record.invoice_payment and record.not_project else False

    @api.depends('invoice_ids', 'invoice_ids.payment_state')
    def _compute_invoice_payment(self):
        for record in self:
            invoice_payment = False
            if record.invoice_ids:
                inv_paid = record.invoice_ids.filtered(lambda i: i.payment_state == 'paid')
                if inv_paid:
                    invoice_payment = True
            record.invoice_payment = invoice_payment


    # def _action_confirm(self):
    #     """ On SO confirmation, some lines should generate a task or a project. """
    #     result = super()._action_confirm()
    #     for order in self:
    #         # not_project = Crear proyecto de forma manual para equipo de ventas
    #         if not order.not_project or order.perm_can_project:
    #             order.order_line.sudo().with_company(order.company_id)._timesheet_service_generation()
    #     return result

    def action_confirm_custom(self):
        for record in self:
            record.action_continue_process()

    def action_confirm(self):
        for record in self:
            record.eval_fields()
            if record.eval_limits():
                return super(SaleOrder, self).action_confirm()
            else:
                self.sudo().write({'state': 'pending'})

    def action_continue_process(self):
        for record in self:
            record.eval_fields()
            if record.eval_limits():
                _request = self._exist_request_by_category(category='check_list')
                if _request and _request.request_status == 'approved':
                    return super(SaleOrder, self).action_confirm()
                else:
                    self.sudo().write({'state': 'compliance'})
            else:
                self.sudo().write({'state': 'pending'})

    def action_confirm_order(self):
        # not_check = self.check_list_lines.filtered(lambda c: not c.check)
        # if not_check:
        #     raise ValidationError(_("Hay un proceso en el check list que no se ha completado. Paso : %s" % not_check.check_list_id.name))
        self.action_confirm()


    def refresh_state(self):
        self._compute_approval_required()
        form = Form(self)
        form.save()

    def eval_limits(self):
        # Evaluacion de margen
        _logger.info("ALIADAS: Evaluación de margen y lista de precios.")
        continue_process = True
        if self.margin_test < self.env.company.sale_margin and self.purchase_ids:
            _logger.info("ALIADAS: Evaluación de margen.")
            _request = self._exist_request_by_category(category='sale_margin')
            if not _request:
                continue_process = False
                self._create_request('margin')

        # Evalación para lista de preocios
        line_approved_required = self.order_line.filtered(lambda l: l.approved_required)
        if line_approved_required:
            # Alguna de las líneas SI requiere aprobación
            user_in = self.pricelist_id.user_ids.filtered(lambda u: u.id == self.env.user.id)
            if not user_in:
                _logger.info("ALIADAS: Evaluación de lista de precios.")
                _request = self._exist_request_by_category(category='list_price')
                if not _request:
                    continue_process = False
                    self._create_request('pricelist')

        #Evaluación de lista de procesos
        lines_check = self.check_list_lines.filtered(lambda c: not c.check or c.date_due < datetime.now().date())
        if lines_check and self.state == 'compliance':
            _logger.info("ALIADAS : Se encontraron líneas que no tienen marcado el check o han vencido")
            _request = self._exist_request_by_category(category='check_list')
            if not _request:
                continue_process = False
                self._create_request('check_list')

        return continue_process

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

    def _exist_request_by_category(self, category):

        payment_term_id = self.env['approval.category'].sudo().search([('approval_type','=','payment_term'),('company_id','=',self.company_id.id)], limit=1)
        list_price_id = self.env['approval.category'].sudo().search([('approval_type','=','pricelist'),('company_id','=',self.company_id.id)], limit=1)
        sale_margin_id = self.env['approval.category'].sudo().search([('approval_type','=','sale_margin'),('company_id','=',self.company_id.id)], limit=1)
        check_list_id = self.env['approval.category'].sudo().search([('approval_type','=','check_list'),('company_id','=',self.company_id.id)], limit=1)

        LIST_CAT = {
            'payment_term': payment_term_id.id,
            'list_price': list_price_id.id,
            'sale_margin': sale_margin_id.id,
            'check_list': check_list_id.id,
        }
        category_id = LIST_CAT[category]
        _request = self.approval_request_ids.filtered(lambda a: a.category_id.id == category_id)
        return _request

    def _create_request(self, mode):
        sale_margin_diff = 0
        if mode == 'margin':
            category_id = self.env['approval.category'].sudo().search([('approval_type','=','sale_margin'),('company_id','=',self.company_id.id)], limit=1)
            sale_margin_diff = self.env.company.sale_margin - self.margin_test
        elif mode == 'pricelist':
            category_id = self.env['approval.category'].sudo().search([('approval_type','=','pricelist'),('company_id','=',self.company_id.id)], limit=1)
        elif mode == 'payment_term':
            category_id = self.env['approval.category'].sudo().search([('approval_type','=','payment_term'),('company_id','=',self.company_id.id)], limit=1)
        elif mode == 'check_list':
            category_id = self.env['approval.category'].sudo().search([('approval_type','=','check_list'),('company_id','=',self.company_id.id)], limit=1)

        if not category_id:
            raise ValidationError(_("Proceso no contemplado para evaluación de aprobación"))

        employee = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)], limit=1)
        if not employee:
            raise ValidationError(_("Para crear una solicitud el usuario %s debe estar relacionado a un empleado" % self.env.user.name))

        if not employee.department_id:
            raise ValidationError(_("Para crear una solicitud el empleado %s debe tener relacionado un departamento" % employee.name))

        _request = self.env['approval.request'].create({
            'category_id': category_id.id,
            'date_start': fields.Datetime.now(),
            'date_end': fields.Datetime.now(),
            'partner_id': self.env.user.partner_id.id,
            'reference': self.name,
            'origin': self.name,
            'sale_id': self.id,
            'pricelist_id': self.pricelist_id.id if mode == 'pricelist' and self.pricelist_id else False,
            'sale_margin_diff': sale_margin_diff,
            'request_owner_id': self.env.user.id,
            'department_id': employee.department_id.id

        })
        if _request:
            self.approval_request_ids += _request
            _request.sudo().action_confirm()

    @api.depends('purchase_ids')
    def _compute_margin_sale(self):
        for record in self:
            margin_sale = 0
            margin_test = 0
            if record.purchase_ids:
                p_amount_untaxed = sum(purchase.amount_untaxed for purchase in record.purchase_ids)
                amount_untaxed = record.amount_untaxed
                if amount_untaxed == 0.0:
                    raise ValidationError(_("El monto de la orden es cero, valide el precio o la cantidad de las líneas."))
                margin_sale = amount_untaxed - p_amount_untaxed
                margin_test = round((margin_sale / amount_untaxed), 2)
            record.margin_sale = margin_sale
            record.margin_test = margin_test

    # TODO: ********************************************** PROCESO DE ALQUILER **********************************************
    @api.onchange('pricelist_id', 'order_line')
    def _onchange_pricelist_id(self):
        self._eval_lines_pricelist()
        super(SaleOrder, self)._onchange_pricelist_id()
        #self._add_rental_line()

    def _add_rental_line(self):
        for record in self:
            product_rental_id = self.env.ref('bpc_aliadas.rental_product_bpc')
            line_rental = record.order_line._filtered_rental()
            line_local = record.order_line._filtered_local()
            if line_local:
                product_uom_qty = sum(line.product_uom_qty for line in line_local)
                if not line_rental:
                    price_unit = line_local[0].price_unit
                    data = [(0, 0, {
                        'product_id': product_rental_id.id,
                        'name': product_rental_id.name,
                        'product_uom_qty': product_uom_qty,
                        'product_uom': product_rental_id.uom_id.id,
                        'price_unit': price_unit
                    })]
                    record.sudo().write({'order_line': data})
                elif line_rental:
                    price_unit_first = line_local[0].price_unit if line_local else False
                    price_unit = line_rental.price_unit
                    if price_unit_first:
                        find_distinct = line_local.filtered(lambda l: l.price_unit != price_unit_first)
                        if not find_distinct:
                            price_unit = price_unit_first
                    line_rental.sudo().write({
                        'product_uom_qty': product_uom_qty,
                        'price_unit': price_unit
                    })

    def _prepare_subscription_data(self, template):
        values = super(SaleOrder, self)._prepare_subscription_data(template)
        if self.is_rental_order:
            lines = self.order_line
            lines_local = lines._filtered_local()

            if lines_local:
                pickup_dates = lines_local.mapped('pickup_date')
                return_dates = lines_local.mapped('return_date')
                min_pickup_date = min(pickup_dates) + timedelta(hours=6)
                max_return_date = max(return_dates) + timedelta(hours=6)
                recurring_invoice_day = min_pickup_date.day

                values.update({
                    'date_start': min_pickup_date.date(),
                    'date_end': max_return_date.date(),
                    'recurring_next_date': False,  # Sera colocado de forma manual
                    'recurring_invoice_day': recurring_invoice_day,  # Sera colocado de forma manual
                })

        return values


    def eval_fields(self):
        for record in self:
            for line in record.order_line:
                rental_type = line.rental_type
                name = line.product_id.name
                if rental_type in ('consumption','consumption_min','consumption_fixed') and not record.hide_columns_mim_max and \
                        self.env.user.has_group('bpc_aliadas.group_aliadas_sale_min_max_editable'):
                    if (not line.amount_min or line.amount_min == 0.0) and (not line.amount_max or line.amount_max == 0.0):
                        raise ValidationError(_("Asegúrese de tener un valor ingresado en la columna MÍNIMO o MÁXIMO para el producto %s " % name))

                elif rental_type in ('rental_min', 'rental_percentage', 'rental_percentage_top'):
                    if rental_type != 'rental_percentage':
                        if (not line.amount_min or line.amount_min == 0.0) and (not line.amount_max or line.amount_max == 0.0):
                            raise ValidationError(_("Asegúrese de tener un valor ingresado en la columna MÍNIMO o MÁXIMO para el producto %s " % name))
                    elif not line.percentage_sale or line.percentage_sale == 0.0:
                        raise ValidationError(_("Asegúrese de tener un valor ingresado en la columna PORCENTAJE SOBRE VENTAS para el producto %s " % name))


    # #Todo: Restricción para cambio de tarifa
    # @api.onchange('pricelist_id', 'order_line')
        # def _onchange_pricelist_id(self):
    #     self._eval_lines_pricelist()
    #     return super(SaleOrder, self)._onchange_pricelist_id()

    def _eval_lines_pricelist(self):
        for record in self:
            if record.pricelist_id:
                analytic_account_id = record.pricelist_id.analytic_account_id
                if not analytic_account_id:
                    raise ValidationError(_("Asigne por favor una cuenta analítica a la lista de precios %s " % record.pricelist_id.name))

                _find_pricelist = record._eval_local_pricelist()
                if _find_pricelist:
                    continue
                #Evaluación de productos solo para renta
                lines_diff = record.order_line.filtered(lambda l:l.product_id.analytic_account_id != analytic_account_id and l.product_id.rent_ok)
                if lines_diff:
                    for l in lines_diff:
                        if not l.product_id.analytic_account_id:
                            raise ValidationError(_("El producto %s no tiene una cuenta analítica asignada " % l.product_id.name))
                        msg = "La cuenta analítica seleccionada * %s * es diferente a la del producto %s - * %s *" % (analytic_account_id.name,
                                                                                                                      l.product_id.name,
                                                                                                                      l.product_id.analytic_account_id.name
                                                                                                                      )
                        raise ValidationError(_(msg))

    def _eval_local_pricelist(self):
        _find_pricelist = False
        if self.order_line:
            lines_local = self.order_line._filtered_local()
            if len(lines_local) == 1:
                if isinstance(lines_local[0].id, models.NewId):
                    _find_pricelist = self.env['product.pricelist'].sudo().search([('analytic_account_id','=',lines_local[0].product_id.analytic_account_id.id),
                                                                                   ('is_start','=',True)], limit=1)
                    if _find_pricelist:
                        _logger.info("ALIADADAS: Orden %s / Asignando lista de precios de inicio : %s" % (self.name, _find_pricelist.name))
                        self.pricelist_id = _find_pricelist
                        #lines_local.pricelist_id = _find_pricelist
            if _find_pricelist:
                for l in self.order_line:
                    l.pricelist_id = _find_pricelist
        return _find_pricelist



    @api.onchange('sale_order_template_id')
    def onchange_sale_order_template_id(self):

        if not self.sale_order_template_id:
            self.require_signature = self._get_default_require_signature()
            self.require_payment = self._get_default_require_payment()
            return

        template = self.sale_order_template_id.with_context(lang=self.partner_id.lang)

        # --- first, process the list of products from the template
        order_lines = [(5, 0, 0)]
        for line in template.sale_order_template_line_ids:
            data = self._compute_line_data_for_template_change(line)

            if line.product_id:
                price = line.product_id.lst_price
                discount = 0

                if self.pricelist_id:
                    pricelist_price = self.pricelist_id.with_context(uom=line.product_uom_id.id).get_product_price(line.product_id, 1, False)

                    if self.pricelist_id.discount_policy == 'without_discount' and price:
                        discount = max(0, (price - pricelist_price) * 100 / price)
                    else:
                        price = pricelist_price

                data.update({
                    'price_unit': price,
                    'discount': discount,
                    'product_uom_qty': line.product_uom_qty,
                    'product_id': line.product_id.id,
                    'document_type_sale_id': line.product_id.document_type_sale_id.id if line.product_id.document_type_sale_id else False,
                    'rental_type': line.product_id.rental_type if line.product_id.rental_type else False,
                    'product_uom': line.product_uom_id.id,
                    'customer_lead': self._get_customer_lead(line.product_id.product_tmpl_id),
                    'subscription_template_id': line.product_id.subscription_template_id if line.product_id.subscription_template_id else False
                })

            order_lines.append((0, 0, data))

        self.order_line = order_lines
        self.order_line._compute_tax_id()

        # then, process the list of optional products from the template
        option_lines = [(5, 0, 0)]
        for option in template.sale_order_template_option_ids:
            data = self._compute_option_data_for_template_change(option)
            option_lines.append((0, 0, data))

        self.sale_order_option_ids = option_lines

        if template.number_of_days > 0:
            self.validity_date = fields.Date.context_today(self) + timedelta(template.number_of_days)

        self.require_signature = template.require_signature
        self.require_payment = template.require_payment

        if not is_html_empty(template.note):
            self.note = template.note

    @api.onchange('order_line')
    def _onchange_order_line(self):
        for record in self:
            if record.order_line:
                lines_local = record.order_line._filtered_local()
                for line in record.order_line:
                    if line.product_id and line.rental_type == 'm2' and not line.product_id.rent_ok:
                        total = sum(line.product_uom_qty for line in lines_local)
                        line.product_uom_qty = total

                    if line.product_id and lines_local and not line.not_update_price and not line.product_id.rent_ok:
                        tmpl_id = line.product_id.product_tmpl_id
                        total_qty = sum(line.product_uom_qty for line in lines_local)
                        lc = lines_local[0]
                        #for lc in lines_local:
                        categ_local_id = lc.product_id.product_tmpl_id.categ_id
                        classification_id = lc.product_id.product_tmpl_id.classification_id
                        pp_items = self.env['product.pricelist.item'].sudo().search([('product_tmpl_id','=',tmpl_id.id),('combination_type','!=',False)])
                        if pp_items:
                            for pp_item in pp_items:
                                if pp_item.combination_type == 'category' and pp_item.category_add_id.id == categ_local_id.id:
                                    line.price_unit = pp_item.fixed_price
                                    line.price_min = pp_item.fixed_price
                                    line.pricelist_id = pp_item.pricelist_id
                                elif pp_item.combination_type == 'classification' and classification_id and pp_item.classification_id.id == classification_id.id:
                                    line.price_unit = pp_item.fixed_price
                                    line.price_min = pp_item.fixed_price
                                    line.pricelist_id = pp_item.pricelist_id
                                elif pp_item.combination_type == 'meter' and pp_item.meter_init <= total_qty <= pp_item.meter_end:
                                    line.price_unit = pp_item.fixed_price
                                    line.price_min = pp_item.fixed_price
                                    line.pricelist_id = pp_item.pricelist_id


    #TODO: ---------------- CRM ------------------
    def _change_stage_opportunity(self, vals):
        """Cambiar el estado de la oportunidad"""
        if type(vals) == dict:
            if 'opportunity_id' in vals:
                lead_id = self.env['crm.lead'].sudo().sudo().browse(vals['opportunity_id'])
                if lead_id and len(lead_id.order_ids.ids) == 1:
                    lead_id.sudo().lead_next_stage('quote')

    def _state_lead(self, vals):
        lead_id = self.opportunity_id
        if lead_id:
            if 'state' in vals:
                if vals['state'] == 'sent' and lead_id.stage_id.type_stage in ('quote','negotiation'):
                    lead_id.lead_next_stage('quote_send')
                elif vals['state'] == 'sale' and lead_id.stage_id.type_stage == 'document_review':
                    lead_id.lead_next_stage('contract')
                elif vals['state'] == 'cancel':
                    lead_id.lead_next_stage('negotiation')
            elif 'accept_and_signed' in vals:
                if vals['accept_and_signed'] and lead_id.stage_id.type_stage == 'quote_send':
                    lead_id.lead_next_stage('document_review')

    def _split_subscription_lines(self):
        """Split the order line according to subscription templates that must be created."""
        self.ensure_one()
        res = dict()
        new_sub_lines = self.order_line.filtered(lambda l: not l.subscription_id and l.subscription_template_id and l.product_id.recurring_invoice)
        #templates = new_sub_lines.mapped('product_id').mapped('subscription_template_id')
        templates = new_sub_lines.mapped('subscription_template_id')
        for template in templates:
            lines = self.order_line.filtered(lambda l: l.subscription_template_id == template and l.product_id.recurring_invoice)
            res[template] = lines
        return res

    def _get_data_report(self, param):
        return sale.report.get_data(self, param)

    @api.depends('order_line.price_total')
    def _amount_all(self):
        """
        Compute the total amounts of the SO.
        """
        for order in self:
            amount_untaxed = amount_tax = 0.0
            for line in order.order_line.filtered(lambda l: not l.product_id.not_total):
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax
            order.update({
                'amount_untaxed': amount_untaxed,
                'amount_tax': amount_tax,
                'amount_total': amount_untaxed + amount_tax,
            })


    # def action_quotation_send(self):
    #     ''' Opens a wizard to compose an email, with relevant mail template loaded by default '''
    #     self.ensure_one()
    #     template_id = self._find_mail_template()
    #     lang = self.env.context.get('lang')
    #     template = self.env['mail.template'].browse(template_id)
    #     if template.lang:
    #         lang = template._render_lang(self.ids)[self.id]
    #     ctx = {
    #         'default_model': 'sale.order',
    #         'default_res_id': self.ids[0],
    #         'default_use_template': bool(template_id),
    #         'default_template_id': template_id,
    #         'default_composition_mode': 'comment',
    #         'mark_so_as_sent': True,
    #         'custom_layout': "mail.mail_notification_paynow",
    #         'proforma': self.env.context.get('proforma', False),
    #         'force_email': True,
    #         'model_description': self.with_context(lang=lang).type_name,
    #         'default_partner_ids': self.partner_prospect_id.ids,
    #         'default_partner_prospect_id': self.partner_prospect_id.id
    #     }
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'view_mode': 'form',
    #         'res_model': 'mail.compose.message',
    #         'views': [(False, 'form')],
    #         'view_id': False,
    #         'target': 'new',
    #         'context': ctx,
    #     }



class SaleOrderChecklistLines(models.Model):
    _name = "sale.order.check_list.lines"
    _description = 'Chek list en orden de venta'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    sale_id = fields.Many2one('sale.order', string='Orden venta')
    check_list_id = fields.Many2one('sale.order.check_list', string='Paso')
    check_list_id_sequence = fields.Integer(related='check_list_id.sequence')
    check = fields.Boolean(string='Check')
    description = fields.Char(string='Observación')
    date_due = fields.Date(string='F.Vencimiento')
    user_ids = fields.Many2many('res.users')

    now = fields.Date(compute='_compute_now')

    def _compute_now(self):
        for record in self:
            record.now = datetime.now().date()

    @api.model
    def _cron_due_check_list(self):
        list_process = self.sudo().search([('sale_id.state', '=', 'compliance'), '|', ('date_due', '<', datetime.today().date()), ('date_due','=',False)])
        for lp in list_process:
            _logger.info("ALIADAS: Evaluando chek list de procesos ID %s correspondiente a la orden %s" % (lp.id, lp.sale_id.name))
            lp.sudo()._create_activity()

    def _create_activity(self):
        for record in self:
            if record.user_ids:
                _logger.info("ALIADAS: Creando notificación...")
                for user_id in record.user_ids:
                    record.sudo().activity_schedule('bpc_aliadas.mail_activity_data_check_list_process',
                                                    user_id=user_id.id,
                                                    note='Referencia a Orden %s' % record.sale_id.name)
            else:
                _logger.info("ALIADAS: No se crea notificación, no tiene usuarios.")
