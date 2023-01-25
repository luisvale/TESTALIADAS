# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, Command, fields, models, _
from collections import defaultdict
from datetime import date, datetime
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)

CATEGORY_SELECTION = [
    ('required', 'Requerido'),
    ('optional', 'Opcional'),
    ('no', 'Ninguno')]

SELECTION_ADD = [('purchase_advance', 'Permitir anticipo (Ventas)'),
                 ('purchase_requisition', 'Licitación (Compras)'),
                 ('purchase_budget', 'Presupuesto (Compras)'),
                 ('purchase_approved', 'Aprobación de compra (Compras)'),
                 ('job_position', 'Puesto de trabajo (RRHH)'),
                 ('sale_margin', 'Margen de ventas (Ventas)'),
                 ('pricelist', 'Lista de precios (Ventas)'),
                 ('check_list', 'Check-list procesos (Ventas)'),
                 ('payment_term', 'Plazos de pago (Ventas)'),
                 ('subs_new_product', 'Nuevo producto (Subscripción)'),
                 ]


class ApprovalCategory(models.Model):
    _inherit = 'approval.category'

    approval_type = fields.Selection(selection_add=SELECTION_ADD, string='Tipo aprobación')
    has_price_unit = fields.Selection(CATEGORY_SELECTION, string="Precio", default="no")

    def create_request(self):
        self.ensure_one()
        # If category uses sequence, set next sequence as name
        # (if not, set category name as default name).

        employee_id = self.env['hr.employee'].sudo().search([('user_id', '=', self.env.user.id)], limit=1)
        if not employee_id:
            _logger.info("Empleado no encontrado")
        return {
            "type": "ir.actions.act_window",
            "res_model": "approval.request",
            "views": [[False, "form"]],
            "context": {
                'form_view_initial_mode': 'edit',
                'default_name': _('New') if self.automated_sequence else self.name,
                'default_category_id': self.id,
                'default_request_owner_id': self.env.user.id,
                'default_request_status': 'new',
                'default_department_id': employee_id.department_id.id if self.approval_type == 'purchase_requisition' and employee_id and employee_id.department_id else False
            },
        }


class ApprovalRequest(models.Model):
    _inherit = 'approval.request'
    _order = 'id desc'

    active = fields.Boolean(default=True, tracking=True, string='Activo')
    user_id = fields.Many2one('res.users', 'Usuario', default=lambda self: self.env.user, store=True, readonly=True)

    @api.model
    def _domain_analytic(self):
        analytic_ids = self.env.user.analytic_ids
        a_ids = analytic_ids.mapped('analytic_id')
        return [('id', 'in', a_ids.ids)]

    def _default_analytic(self):
        analytic_ids = self.env.user.analytic_ids
        a_ids = analytic_ids.filtered(lambda a: a.default)
        if a_ids:
            return a_ids.analytic_id
        else:
            return False

    analytic_account_id = fields.Many2one('account.analytic.account', domain=_domain_analytic, default=_default_analytic)
    sale_id = fields.Many2one('sale.order', string='Orden venta')
    purchase_id = fields.Many2one('purchase.order', string='Orden compra')
    purchase_advance_amount = fields.Float(related='purchase_id.advance_amount', string='Anticipo de orden')
    advance_payment_method = fields.Selection([('percentage', 'Porcentaje'), ('fixed', 'Monto fijo')], string='Tipo anticipo', default='percentage')  # P2 - Anticipo
    advance_amount = fields.Float(string='Nuevo monto anticipo')  # P2 - Anticipo
    requisition_id = fields.Many2one('purchase.requisition', string='Licitación', store=True, readonly=True)
    requisition_currency_id = fields.Many2one('res.currency', string='Moneda')
    has_price_unit = fields.Selection(related="category_id.has_price_unit")
    job_id = fields.Many2one('hr.job', string='Puesto de trabajo', store=True, readonly=True)
    department_id = fields.Many2one('hr.department', string='Departamento')
    origin = fields.Char(string='Origen', help='Documento desde donde viene la solicitud')
    pricelist_id = fields.Many2one('product.pricelist', string='Lista de precios a aprobar')
    subscription_id = fields.Many2one('sale.subscription', string='Subscripción')
    product_ids = fields.Many2many('product.product', string='Productos')
    sale_margin_diff = fields.Float(string='Diferencia en margen')

    link_approval = fields.Char(string='Link aprobación')

    # @api.depends('approver_ids.status', 'approver_ids.required')
    # def _compute_request_status(self):
    #     super(ApprovalRequest, self)._compute_request_status()
    #

    # @api.onchange('purchase_id')
    # def _onchange_purchase_id(self):
    #     for record in self:
    #         if record.purchase_id and record.approval_type == 'purchase_advance':
    #             if record.purchase_id.partner_id.advance_amount in [0.0, False]:
    #                 raise ValidationError(_("No puede aplicar anticipo a esta orden de compra puesto que el proveedor no tiene un monto asignado."))

    def _eval_conditions(self):
        for record in self:
            category_id = record.category_id
            if record.request_status == 'approved':
                if category_id.id == self.env.ref('bpc_aliadas.approval_category_data_purchase_advance').id and record.purchase_id:
                    if not record.purchase_id.approval_request_advance:
                        record.purchase_id.sudo().write({'approval_request_advance': record.id})

                # elif category_id.id == self.env.ref('bpc_aliadas.approval_category_data_purchase_general').id:
                #     order_id = self.env['purchase.order'].sudo().search([('name','=', record.origin)])
                #     if order_id:
                #         approver_id = record.approver_ids.filtered(lambda a: a.user_id.id == record.env.user.id)
                #         if approver_id:
                #             amount_permission = approver_id.amount
                #             if amount_permission < order_id.amount_total:
                #                 raise ValidationError(_("Estimado %s . Usted no puede aprobar esta solicitud, puesto que el monto de la orden de compra %s excede"
                #                                         " a lo que tiene ud permitido." % (record.env.user.name, order_id.name)))

                elif record.approval_type == 'purchase_requisition':
                    _logger.info("ALIADAS: Creando licitación de forma automática")
                    record.sudo().create_purchase_requisition()

                else:
                    pass

    def create_purchase_requisition(self):
        # Creacion de requisito de compra (LICITACION)
        def _get_lines(product_line_ids, self):
            list_lines = []
            if product_line_ids:
                for l in product_line_ids:
                    list_lines.append((0, 0, {
                        'product_id': l.product_id.id,
                        'product_description_variants': l.description,
                        'product_qty': l.quantity,
                        'price_unit': l.price_unit,
                        'account_id': l.account_id.id if l.account_id else False,
                        'account_analytic_id': l.analytic_id.id if l.analytic_id else False,
                        'product_uom_id': l.product_uom_id.id if l.product_uom_id else False,
                        # 'account_analytic_id': self.analytic_account_id.id if self.analytic_account_id else False
                    }))

            return list_lines

        lines = _get_lines(self.product_line_ids, self)
        try:
            requisition_new = self.env['purchase.requisition'].sudo().create({
                'line_ids': lines,
                'user_id': self.user_id.id,
                'vendor_id': self.partner_id.id,
                'currency_id': self.requisition_currency_id.id if self.requisition_currency_id else self.env.user.company_id.currency_id.id,
                'ordering_date': self.date,
                'analytic_account_id': self.analytic_account_id.id if self.analytic_account_id else False,
                'department_id': self.department_id.id if self.department_id else False,
                'request_id': self.id
            })
            if requisition_new:
                msg = 'ALIADAS: Licitación con ID * %s * creado ' % requisition_new.id
                self.sudo().write({'requisition_id': requisition_new.id})
            else:
                msg = 'ALIADAS: Error en la creación de licitación'
            _logger.info(msg)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'title': _('Bien!'),
                    'message': _("La licitación ha sido creada correctamente."),
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }
        except KeyError as e:
            raise ValidationError(_("Error en la creación de licitación: %s" % e))

    def create_job_position(self):
        job = self.env['hr.job'].create({
            'name': self.reference,
            'department_id': self.department_id.id,
            'no_of_recruitment': self.quantity,
            'user_id': self.partner_id.user_id,
            'description': self.reason
        })
        if job:
            self.job_id = job

    def _evaluation_department(self, user, record):
        _next = False
        employee_id = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        if employee_id:
            department_id = employee_id.department_id
            if department_id:
                if record.department_id:
                    add = False
                    if department_id.id in record.department_id.departament_ids.ids or department_id.id == record.department_id.id:
                        add = True
                    if add:
                        _next = True
                else:
                    _logger.info("La solicitud no tiene un departament asignado, quizá el propietario no se ecuentra como empleado o no tiene Dep.")
            else:
                _logger.info("El empleado %s no tiene un departamento asignado" % employee_id.name)
        else:
            _logger.info("Empleado no encontrado")

        return _next

    @api.depends('category_id', 'request_owner_id')
    def _compute_approver_ids(self):
        for request in self:
            # Don't remove manually added approvers
            users_to_approver = defaultdict(lambda: self.env['approval.approver'])
            for approver in request.approver_ids:
                users_to_approver[approver.user_id.id] |= approver
            users_to_category_approver = defaultdict(lambda: self.env['approval.category.approver'])
            for approver in request.category_id.approver_ids:
                users_to_category_approver[approver.user_id.id] |= approver
            new_users = request.category_id.user_ids #usuarios a evaluar
            if request.approval_type in ('purchase_approved', 'purchase_budget'):
                user_ids = request.department_id.authorization_line_ids.mapped('user_id')
                new_users = user_ids #completo con los usuarios de las autorizaciones por dpto
            manager_user = 0
            employee = self.env['hr.employee'].search([('user_id', '=', request.request_owner_id.id)], limit=1)
            if request.category_id.manager_approval:
                if employee.parent_id.user_id:
                    new_users |= employee.parent_id.user_id
                    manager_user = employee.parent_id.user_id.id
            if employee and request.approval_type not in ('purchase_approved','purchase_budget'):
                if employee.department_id:
                    _logger.info("Empleado encontrado. Se añade departamento %s" % employee.department_id.name)
                request.department_id = employee.department_id
            approver_id_vals = []
            for user in new_users:
                # Force require on the manager if he is explicitely in the list
                required = users_to_category_approver[user.id].required or \
                           (request.category_id.manager_approval == 'required' if manager_user == user.id else False)
                current_approver = users_to_approver[user.id]
                if current_approver and current_approver.required != required:
                    approver_id_vals.append(Command.update(current_approver.id, {'required': required}))
                elif not current_approver:
                    level_id = users_to_category_approver[user.id].level_id
                    # if required:  # Custom para aliadas
                    # if request.approval_type == 'sale_margin' and users_to_category_approver[user.id].percentage_margin >= request.sale_margin_diff:
                    if request.approval_type == 'sale_margin' and request.sale_id:
                        _next = self._evaluation_department(user, request)
                        _logger.info('_NEXT: %s ' % _next)
                        if _next:
                            line = self.env['approval.interval.line'].sudo()
                            amount_lines_ids = users_to_category_approver[user.id].amount_lines
                            for a in amount_lines_ids:
                                if a.percentage_from <= request.sale_margin_diff <= a.percentage_to:
                                    line += a
                            if line:
                                approver_id_vals.append(Command.create({
                                    'user_id': user.id,
                                    'status': 'new',
                                    'required': required,
                                    'amount': users_to_category_approver[user.id].amount,
                                    'pricelist_ids': False,
                                    'level_id': level_id.id if level_id else False,
                                    'amount_lines': [(6, 0, line.ids)] if line else False,
                                }))

                    elif request.approval_type == 'purchase_requisition':
                        _next = self._evaluation_department(user, request)
                        _logger.info('_NEXT: %s ' % _next)
                        if _next:
                            approver_id_vals.append(Command.create({
                                'user_id': user.id,
                                'status': 'new',
                                'required': required,
                                'amount': users_to_category_approver[user.id].amount,
                                'pricelist_ids': False,
                                'level_id': level_id.id if level_id else False
                            }))

                    elif request.approval_type in ('purchase_approved', 'purchase_budget') and request.purchase_id:
                        if request.department_id:
                            _next = self._evaluation_department(user, request)
                            _logger.info('_NEXT: %s ' % _next)
                            if _next:
                                amount_total = request.purchase_id.amount_total
                                currency_id = request.purchase_id.currency_id
                                line = self.env['authorization.interval.line'].sudo()
                                # amount_lines_ids = users_to_category_approver[user.id].amount_lines
                                _logger.info("APROBACIÓN: Aprobación de compra - departamento %s " % request.department_id.name)
                                if request.department_id.authorization_line_ids:
                                    amount_lines_id = self.env['department.authorization.line'].sudo().search([('department_id', 'in', request.department_id.ids),
                                                                                                                ('company_id', '=', request.company_id.id),
                                                                                                                ('user_id', '=', user.id)], limit=1)

                                    if amount_lines_id:
                                        for a in amount_lines_id.amount_lines:
                                            if currency_id != a.currency_id:
                                                amount_convert = currency_id._convert(amount_total, a.currency_id, request.company_id, request.purchase_id.date_order or date.today)
                                                if a.amount_from <= amount_convert <= a.amount_to:
                                                    line += a
                                                    break
                                            else:
                                                if a.amount_from <= amount_total <= a.amount_to:
                                                    line += a
                                                    break

                                        if line:
                                            approver_id_vals.append(Command.create({
                                                'user_id': user.id,
                                                'status': 'new',
                                                'required': required,
                                                'amount': users_to_category_approver[user.id].amount,  # Personalizado para aliadas
                                                #'amount_lines': [(6, 0, line.ids)] if line else False,
                                                'interval_amount_lines': [(6, 0, amount_lines_id.amount_lines.ids)] if amount_lines_id.amount_lines else False,
                                                'level_id': amount_lines_id.level_id.id
                                            }))
                                    else:
                                        _logger.info("APROBACIÓN: No hay intervalos encontrados")
                                else:
                                    _logger.info("APROBACIÓN : No hay autorizaciones ligadas a este departamento")

                    else:
                        _next = self._evaluation_department(user, request)
                        _logger.info('_NEXT: %s ' % _next)
                        if _next:
                            pricelist_ids = users_to_category_approver[user.id].pricelist_ids
                            approver_id_vals.append(Command.create({
                                'user_id': user.id,
                                'status': 'new',
                                'required': required,
                                'amount': users_to_category_approver[user.id].amount,  # Personalizado para aliadas
                                'pricelist_ids': [(6, 0, pricelist_ids.ids)] if pricelist_ids else False,
                                'level_id': level_id.id if level_id else False
                            }))
            request.update({'approver_ids': approver_id_vals})

    def act_view_approval_request(self):
        for record in self:
            if record.request_status == 'pending':
                record.action_approve()

    def act_view_refused_request(self):
        for record in self:
            if record.request_status == 'pending':
                record.action_refuse()

    def action_confirm(self):
        # self._eval_departmens()
        self._eval_purchase_advance()
        if self.category_id.manager_approval == 'required':
            employee = self.env['hr.employee'].search([('user_id', '=', self.request_owner_id.id)], limit=1)
            if not employee.parent_id:
                raise UserError(_('This request needs to be approved by your manager. There is no manager linked to your employee profile.'))
            if not employee.parent_id.user_id:
                raise UserError(_('This request needs to be approved by your manager. There is no user linked to your manager.'))
            if not self.approver_ids.filtered(lambda a: a.user_id.id == employee.parent_id.user_id.id):
                raise UserError(_('This request needs to be approved by your manager. Your manager is not in the approvers list.'))
        if len(self.approver_ids) < self.approval_minimum and self.approval_type not in ('purchase_approved', 'purchase_budget'):
            raise UserError(_("You have to add at least %s approvers to confirm your request.", self.approval_minimum))
        if self.requirer_document == 'required' and not self.attachment_number:
            raise UserError(_("You have to attach at lease one document."))
        approvers = self.mapped('approver_ids').filtered(lambda approver: approver.status == 'new')
        approvers._create_activity()
        approvers._create_url()
        approvers._send_email()
        approvers.write({'status': 'pending'})
        self.write({'date_confirmed': fields.Datetime.now()})

    def _create_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        request = self
        action = self.env.ref('approvals.approval_request_action')
        menu = self.env.ref('approvals.approvals_request_menu_my')
        url = "/web#id=%s&action=%s&model=approval.request&view_type=form&menu_id=%s" % (request.id, action.id, menu.id)

        complete_url = '%s%s' % (base_url, url)

        self.sudo().write({'link_approval': complete_url})

        _logger.info("URL de aprobación generada : %s " % complete_url)

    def _send_email(self):
        if not self.approver_ids:
            _logger.info("No hay aprobadores para enviar email")
        for line in self.approver_ids:
            template = self.env.ref('bpc_aliadas.approval_template_approver_user', raise_if_not_found=False)
            try:
                email_values = {
                    'email_from': self.env.user.email_formatted,
                    'author_id': self.env.user.partner_id.id,
                }
                res = template.sudo().send_mail(line.id,
                                                notif_layout='mail.mail_notification_light',
                                                force_send=True,
                                                email_values=email_values)
                _logger.info("Resultado del envío a usuario %s es : %s " % (line.user_id.name, res))
            except Exception as e:
                _logger.warning("Error de envío a aprobador: %s " % e)


    def send_mail_approval(self):
        self.ensure_one()
        self._create_url()
        self._send_email()


    #
    # def _eval_departmens(self):
    #     for record in self:
    #         if record.approval_type in ('purchase_requisition', 'job_position', 'purchase'):
    #             department_id = record.department_id
    #
    #             find_not_dep = record.approver_ids.filtered(lambda a: a.department_id != department_id)
    #             find_related = record.approver_ids.filtered(lambda a: a.department_id.id in department_id.departament_ids.ids)
    #             if find_not_dep and not find_related:
    #                 for line in find_not_dep:
    #                     aut_name = line.user_id.name
    #                     raise ValidationError(_("El autorizador %s no pertenece al departamento(%s) de la solicitud."
    #                                             "Asegúrese de enviar a autorizadores que coincidan con este departamento. O al menos que "
    #                                             "estos coindican como departamentos relacionados." % (aut_name, department_id.name)))

    def _eval_purchase_advance(self):
        for record in self:
            if record.approval_type == 'purchase_advance' and record.purchase_id:
                purchase_id = record.purchase_id
                purchase_id.sudo().write({'advance_check': True})

                if record.advance_payment_method:
                    purchase_id.sudo().write({'advance_payment_method': record.advance_payment_method})

                if record.advance_amount > 0.0:
                    purchase_id.sudo().write({'advance_amount': record.advance_amount})

    def action_approve(self, approver=None):
        self._eval_level()
        self._eval_pricelist()
        return super(ApprovalRequest, self).action_approve(approver=approver)

    def _eval_level(self):
        approver = self.mapped('approver_ids').filtered(lambda approver: approver.user_id == self.env.user)
        if not approver.level_id:
            raise ValidationError(_("Para aprobar necesita un NIVEL asignado."))
        level_id = approver.level_id  # Nivel actual de usuario
        others_approver_lines = self.mapped('approver_ids').filtered(lambda a: a.user_id != self.env.user)
        for o in others_approver_lines:
            if o.level_id:
                if o.level_id.sequence < level_id.sequence and o.status != 'approved':
                    raise ValidationError(_("Aún falta la aprobación del: %s " % o.level_id.name))

    def _eval_pricelist(self):
        if self.sale_id and self.approval_type == 'pricelist':
            pricelist_id = self.sale_id.pricelist_id
            approver_line = self.mapped('approver_ids').filtered(lambda approver: approver.user_id == self.env.user)
            if pricelist_id.id not in approver_line.pricelist_ids.ids:
                raise ValidationError(_("No puede aprobar una lista de precios a la cual no tiene autorización. Lista de precio %s " % pricelist_id.name))

    def action_refuse(self, approver=None):
        super(ApprovalRequest, self).action_refuse(approver)
        if not isinstance(approver, models.BaseModel):
            approver = self.mapped('approver_ids').filtered(lambda approver: approver.user_id == self.env.user)
            level_id = approver.level_id  # Nivel actual de usuario
            if not level_id:
                raise ValidationError(_("Usted debería tener un NIVEL DE APROBACIÓN para rechazar la solicitud."))

            # Pasar a cancelado si el nivel de este es el mayor
            others_approver_lines = self.mapped('approver_ids')
            level_ids = others_approver_lines.mapped('level_id')
            sequence_min = min(level_ids.mapped('sequence'))
            if type(sequence_min) == int:
                # Evaluo que el nivel del usuario que rechaza sea del nivel menor, si es así entonces pasará a cancelado
                if sequence_min == level_id.sequence and self.request_status != 'cancel':
                    self.sudo().action_cancel()
        # return res

    @api.depends('approver_ids.status', 'approver_ids.required')
    def _compute_request_status(self):
        for request in self:
            status_lst = request.mapped('approver_ids.status')
            required_statuses = request.approver_ids.filtered('required').mapped('status')
            required_approved = required_statuses.count('approved') == len(required_statuses)
            minimal_approver = request.approval_minimum if len(status_lst) >= request.approval_minimum else len(status_lst)
            if status_lst:
                if status_lst.count('cancel'):
                    status = 'cancel'
                elif status_lst.count('refused'):
                    status = 'refused'
                elif status_lst.count('new'):
                    status = 'new'
                elif request.approval_type in ('purchase_approved', 'purchase_budget') and status_lst.count('approved') < len(request.approver_ids.ids):
                    status = 'pending'
                elif status_lst.count('approved') >= minimal_approver and required_approved:
                    status = 'approved'
                else:
                    status = 'pending'
            else:
                status = 'new'
            request.request_status = status
            #Evaluar condiciones
            request._eval_conditions()


class ApprovalProductLine(models.Model):
    _inherit = 'approval.product.line'

    category_id = fields.Many2one('approval.category', string='Categoría', related='approval_request_id.category_id')
    approval_type = fields.Selection(related='category_id.approval_type', string='Tipo aprobación')
    price_unit = fields.Float("Precio unitario", default=1.0)
    account_id = fields.Many2one('account.account', string='Cuenta')
    analytic_id = fields.Many2one('account.analytic.account', string='Cuenta Analítica')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        super(ApprovalProductLine, self)._onchange_product_id()
        for record in self:
            if record.product_id:
                accounts = self.product_id.product_tmpl_id.get_product_accounts()
                account_id = accounts['expense']
                record.account_id = account_id
            else:
                record.account_id = False


class ApprovalApprover(models.Model):
    _inherit = 'approval.approver'

    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.company.currency_id.id)
    amount = fields.Monetary(string='Monto', copy=False, store=True, readonly=False)
    amount_lines = fields.Many2many('approval.interval.line', string='Montos')
    interval_amount_lines = fields.Many2many('authorization.interval.line', string='Montos.')
    percentage_margin = fields.Float(string='Porcentaje', copy=False, store=True, readonly=False)
    department_id = fields.Many2one('hr.department', string='Departamento', compute='_compute_department_id')
    pricelist_ids = fields.Many2many('product.pricelist', string='Lista de precios')
    level_id = fields.Many2one('approval.level', string='Nivel')

    def unlink(self):
        if self.env.user.has_group('bpc_aliadas.group_aliadas_request_delete'):
            return super(ApprovalApprover, self).unlink()
        else:
            raise ValidationError(_("Ud no tiene permiso para eliminar autorizadores"))

    def _compute_department_id(self):
        for record in self:
            department_id = False
            if record.user_id:
                employee = self.env['hr.employee'].sudo().search([('user_id', '=', record.user_id.id)])
                if employee:
                    department_id = employee.department_id
            record.department_id = department_id

    # def _compute_amount_lines(self):
    #     for record in self:
    #         lines = self.env['approval.interval.line']
    #         for app in record.request_id.approver_ids:
    #             if app.amount_lines:
    #                 lines += app.amount_lines
    #         record.amount_lines = lines


    def name_get(self):
        result = []
        for r in self:
            name = r.user_id.name
            result.append((r.id, name))
        return result

class ApprovalCategoryApprover(models.Model):
    _inherit = 'approval.category.approver'

    level_id = fields.Many2one('approval.level', string='Nivel')
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.company.currency_id.id)
    amount = fields.Monetary(string='Monto', copy=False)
    approval_type = fields.Selection(related='category_id.approval_type', string='Tipo aprobación')
    pricelist_ids = fields.Many2many('product.pricelist', string='Lista de precios')
    percentage_margin = fields.Float(string='Porcentaje')
    amount_lines = fields.One2many('approval.interval.line', 'approval_id', readonly=False, string='Montos')
    department_id = fields.Many2one('hr.department', string='Departamento', compute='_compute_department_id')

    def _compute_department_id(self):
        for record in self:
            department_id = False
            if record.user_id:
                employee = self.env['hr.employee'].sudo().search([('user_id', '=', record.user_id.id)])
                if employee:
                    department_id = employee.department_id
            record.department_id = department_id


class ApprovalIntervalLine(models.Model):
    _name = 'approval.interval.line'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Aprobación con intervalos'

    approval_id = fields.Many2one('approval.category.approver', string='Aprobación')
    category_id = fields.Many2one('approval.category', string='Categoría', related='approval_id.category_id')
    approval_type = fields.Selection(related='category_id.approval_type')
    currency_id = fields.Many2one('res.currency', string='Moneda')
    amount_from = fields.Monetary(string='Desde', default=0.0)
    amount_to = fields.Monetary(string='Hasta', default=0.0)
    percentage_from = fields.Float(string='% Desde', default=0.0)
    percentage_to = fields.Float(string='% Hasta', default=0.0)

    def name_get(self):
        res = []
        for record in self:
            if record.approval_type == 'sale_margin':
                name = 'De {} % a {} % '.format(record.percentage_from, record.percentage_to)
            elif record.approval_type == 'purchase_approved':
                name = 'De %s %s a %s %s ' % (record.currency_id.symbol, record.amount_from, record.currency_id.symbol, record.amount_to)
            else:
                name = '//'
            res.append((record.id, name))
        return res
