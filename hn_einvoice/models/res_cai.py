from odoo import models, api, _, fields
from odoo.exceptions import ValidationError, UserError
from datetime import date, datetime
import logging

_logger = logging.getLogger(__name__)

USED = [('sale', 'Ventas'), ('purchase', 'Compras')]

STATE = [('draft', 'Inactivo'), ('done', 'Activo')]


class ResCai(models.Model):
    _name = 'res.cai'
    _description = 'CAI'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    type_use = fields.Selection(USED, string='Uso', required=True)
    cai = fields.Char('C.A.I', required=True, copy=False)
    range_start = fields.Char('Rango inicio', required=True)
    range_end = fields.Char('Rango final', required=True)
    limit_init = fields.Integer(copy=False)  # Limite inicial - oculto
    limit_end = fields.Integer(copy=False)  # Limite final - oculto
    date_start = fields.Date(string='Fecha inicio', required=True)
    date_end = fields.Date(string='Fecha límite', required=True)
    partner_id = fields.Many2one('res.partner', string='Proveedor')
    state = fields.Selection(STATE, string='Estado', default='draft', copy=False)
    terminal_code = fields.Char(copy=False)
    sucursal_code = fields.Char(copy=False)
    terminal_id = fields.Many2one('company.terminal', copy=False)
    sucursal_id = fields.Many2one('company.sucursal', copy=False)
    document_type_id = fields.Many2one('document.type', 'Tipo documento', copy=False)
    sequence_id = fields.Many2one('ir.sequence', 'Secuencia', copy=False)
    sequence_range_id = fields.Many2one('ir.sequence.date_range', 'Línea específica', copy=False)
    journal_id = fields.Many2one('account.journal', string='Diario')

    next_cai_number = fields.Char(string='Próximo número', compute='_compute_next_cai_number')


    @api.constrains('cai')
    def _check_cai(self):
        for record in self:
            if len(record.cai) != 37:
                raise UserError(_("El código cai debe tener 37 caracteres , tiene ingresado %s" % len(record.cai)))

    @api.constrains('range_start', 'range_end')
    def _check_ranges(self):
        for record in self:
            if len(record.range_start) != 19:
                raise UserError(_("El rango de inicio debe tener 19 caracteres , tiene ingresado %s" % len(record.range_start)))

            if len(record.range_end) != 19:
                raise UserError(_("El rango final debe tener 19 caracteres , tiene ingresado %s" % len(record.range_end)))

    @api.constrains('cai', 'range_start', 'range_end', 'date_start', 'date_end', 'state', 'type_use', 'id')
    def _check_fields(self):
        domain = [('cai', '=', self.cai),
                  ('range_start', '=', self.range_start),
                  ('range_end', '=', self.range_end),
                  ('date_start', '=', self.date_start),
                  ('date_end', '=', self.date_end),
                  ('state', '=', 'done'),
                  ('id', 'not in', self.ids)
                  ]
        if self.type_use == 'sale':
            domain.append(('type_use', '=', 'sale'))
            results = self.sudo().search(domain)
            if len(results) >= 1:
                raise UserError(_("Este cai de clientes ya se encuentra registrado con estado ACTIVO!"))
        elif self.type_use == 'purchase':
            domain.append(('type_use', '=', 'purchase'))
            domain.append(('partner_id', '=', self.partner_id.id))
            results = self.sudo().search(domain)
            if len(results) >= 1:
                raise UserError(_("Este cai ya se encuentra registrado para el proveedor - %s - con estado ACTIVO!" % (self.partner_id.name)))

    @api.constrains('limit_init', 'limit_end')
    def _check_limit_init_end(self):
        if self.limit_init > self.limit_end:
            raise ValidationError(_("El rango de inicio de cai no puede ser mayor al rango final. Por favor revise las secuencias de los rangos."))

    @api.constrains('date_end', 'date_start')
    def _check_date_start_end(self):
        if self.date_start > self.date_end:
            raise ValidationError(_("La fecha de inicio no puede ser mayor a la fecha límite."))

    def name_get(self):
        result = []
        for record in self:
            if record.type_use == 'purchase':
                result.append((record.id, '%s / %s' % (record.partner_id.name, record.cai)))
            else:
                result.append((record.id, '%s / %s' % (record.company_id.name, record.cai)))
        return result

    @api.onchange('range_start', 'range_end')
    def _onchange_limit(self):
        for record in self:
            if record.range_start and record.range_end:
                sp = self._split_cai()
                seq_init = sp['seq_init']
                seq_end = sp['seq_end']
                record.limit_init = int(seq_init)
                record.limit_end = int(seq_end)
                if record.type_use == 'sale':
                    sucursal_code = sp['sucursal_code']
                    sucursal_id = self.env['company.sucursal'].sudo().search([('code', '=', sucursal_code), ('company_id', '=', self.company_id.id)])
                    if not sucursal_id:
                        raise ValidationError(_("No existe alguna sucursal con el código %s para la compañía %s " % (sucursal_code, self.company_id.name)))

                    record.sucursal_id = sucursal_id

    def state_draft(self):
        for record in self:
            record.state = 'draft'

    def state_confirmed(self):
        for record in self:
            record.state = 'done'
            splites = self._split_cai()
            if record.type_use == 'sale':
                process = record._complete_fields_sale(splites)
            elif record.type_use == 'purchase':
                process = record._complete_fields_purchase(splites)

            if process:
                record.journal_id.cai_ids += record
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'type': 'success',
                        'message': _("Confirmación procesada correctamente."),
                        'next': {'type': 'ir.actions.act_window_close'},
                    }
                }

    def _split_cai(self):
        range_start = self.range_start.split('-')
        range_end = self.range_end.split('-')
        return {
            'sucursal_code': range_start[0],
            'terminal_code': range_start[1],
            'document_code': range_start[2],
            'seq_init': range_start[3],
            'seq_end': range_end[3],
            'date_init': self.date_start,
            'date_end': self.date_end,
        }

    def _complete_fields_purchase(self, splites):

        self.terminal_code = splites['terminal_code']
        self.sucursal_code = splites['sucursal_code']
        env_document = self.env['document.type'].sudo()
        document_id = env_document.search([('code', '=', splites['document_code'])])
        self.document_type_id = document_id
        self.limit_init = splites['seq_init']
        self.limit_end = splites['seq_end']
        self.partner_id.lines_cai_ids += self

    def _complete_fields_sale(self, splites):
        self.ensure_one()

        env_sucursal = self.env['company.sucursal'].sudo()
        env_terminal = self.env['company.terminal'].sudo()
        env_document = self.env['document.type'].sudo()

        sucursal_id = env_sucursal.search([('code', '=', splites['sucursal_code']), ('company_id', '=', self.company_id.id)])
        if not sucursal_id:
            raise ValidationError(_("No existe alguna sucursal con código %s dentro de la compañia %s" % (splites['sucursal_code'], self.company_id.name)))

        terminal_id = env_terminal.search([('code', '=', splites['terminal_code']), ('sucursal_id', '=', sucursal_id.id), ('company_id', '=', self.company_id.id)])
        if not terminal_id:
            raise ValidationError(_("No existe alguna terminal con código %s dentro de la compañia %s" % (splites['terminal_code'], self.company_id.name)))

        #Evaluamos diario
        journal_id = self.env['account.journal'].sudo().search([('sucursal_id','=',sucursal_id.id),
                                                                ('terminal_id','=',terminal_id.id),
                                                                ('company_id','=',self.company_id.id)], limit=1)
        if not journal_id:
            raise ValidationError(_("No existe algún diario para sucursal %s - terminal %s dentro de la compañia %s. Cree un diario con estos datos." %
                                    (splites['terminal_code'], splites['terminal_code'], self.company_id.name)))

        document_id = env_document.search([('code', '=', splites['document_code'])])

        model_sequence = self.env['ir.sequence'].sudo()
        if not self.company_id.vat:
            raise ValidationError(_("Es necesario el VAT de la compañía."))

        name = self.company_id.vat + '-' + sucursal_id.code + '-' + terminal_id.code + '-' + document_id.name
        code = self.company_id.vat + '-' + sucursal_id.code + '-' + terminal_id.code + '-' + document_id.code

        data = {
            "name": name,
            "code": code,
            "implementation": "standard",
            "padding": 8,
            "company_id": self.company_id.id,
            'number_next': 1,
            'number_increment': 1,
            'use_date_range': True,
        }

        if not self.sequence_id:
            sequence_id = model_sequence.search([('code', '=', data['code'])])
            if sequence_id:
                self.sequence_id = sequence_id[0]
            else:
                self.sequence_id = model_sequence.create(data)

        date_init = splites['date_init']
        date_end = splites['date_end']
        seq_init = splites['seq_init']
        seq_end = splites['seq_end']
        sequence_range_id = self._search_sequences(date_init, date_end, seq_init)

        self.terminal_id = terminal_id
        self.sucursal_id = sucursal_id
        self.journal_id = journal_id
        self.document_type_id = document_id
        self.limit_init = int(seq_init)
        self.limit_end = int(seq_end)
        self.sequence_range_id = sequence_range_id

        return True

    def _search_sequences(self, date_init, date_end, number):
        env_sequence_range = self.env['ir.sequence.date_range'].sudo()

        seq_date_range = env_sequence_range.search([('sequence_id', '=', self.sequence_id.id),
                                                    ('date_from', '>=', date_init),
                                                    ('date_from', '<=', date_end)],
                                                   order='date_from desc', limit=1)
        data = {
            'date_from': date_init,
            'date_to': date_end,
            'sequence_id': self.sequence_id.id,
            'number_next': number,
        }
        if not seq_date_range:
            seq_date_range = self.env['ir.sequence.date_range'].sudo().create(data)
            _logger.info("BPC - Creando rango de fechas para secuencia %s  - datos: %s" % (self.sequence_id.name, data))
            _logger.info("Número a actualizar %s " % number)
            seq_date_range.sudo().write({'number_next': int(number)})
        else:
            _logger.info("Número a actualizar %s " % number)
            seq_date_range.sudo().write({'number_next': int(number)})
            _logger.info("BPC - Se encontró rango de fechas para secuencia %s - datos: %s " % (self.sequence_id.name, data))

        return seq_date_range

    def _available_cai(self, cai_ids, type):
        now = datetime.now().date()
        cai_id = False
        if type == 'sale':
            cai_id = cai_ids.filtered(lambda c: c.date_start <= now and c.date_end >= now)
            if not cai_id:
                raise ValidationError(_("No hay CAI vigente para la fecha de hoy %s " % now))

            if cai_id.state == 'draft':
                raise ValidationError(_("No hay CAI vigente para la fecha de hoy %s se encuentra en estado borrador por favor pase a estado CONFIRMADO" % now))

        return cai_id

    def _cai_validate_supplier(self, invoice):
        res_cai = False
        message = False

        if not invoice.ref:
            message = "Si desea validar el CAI de esta factura, ingrese el valor en el campo * Referencia Factura * "
        elif len(invoice.ref.split('-')) != 4:
            message = "El campo referencia de factura no tiene el formato adecuado. Se requiere formato 001-001-01-00000001"
        elif not invoice.partner_id:
            message = "Si desea validar el CAI se requiere que seleccione el proveedor, campo * Proveedor * "
        else:

            cai = invoice.ref.split('-')
            sucursal = cai[0]
            terminal = cai[1]
            document_type = cai[2]
            sequence = cai[3]

            res_cai = self.env['res.cai'].sudo().search([('document_type_id.code', '=', document_type),
                                                         ('partner_id', '=', invoice.partner_id.id),
                                                         ('type_use', '=', 'purchase'),
                                                         ('state', '=', 'done'),
                                                         ('date_start', '<=', invoice.invoice_date or datetime.now().date()),
                                                         ('date_end', '>=', invoice.invoice_date or datetime.now().date()),
                                                         ('limit_init','<=',int(sequence)),
                                                         ('limit_end','>=',int(sequence)),
                                                         ('sucursal_code','=',str(sucursal)),
                                                         ('terminal_code','=',str(terminal)),
                                                         ], limit=1)


            if not res_cai:
                message = "No tienen un C.A.I registrado en el sistema con la sucursal %s , terminal %s, documento %s para %s"\
                          % (sucursal, terminal, document_type, invoice.partner_id.name)
            else:
                if res_cai.state == 'draft':
                    message = 'Se econtró un CAI, sin embargo este se encuentra en modo borrador.'
                elif res_cai.sucursal_code != sucursal:
                    message = 'La sucursal del CAI ingresado no es la misma que la del registrado en el sistema.'
                elif res_cai.terminal_code != terminal:
                    message = 'La terminal del CAI ingresado no es la misma que la del registrado en el sistema.'
                elif res_cai.document_type_id.code != document_type:
                    message = 'El tipo de documento del CAI ingresado no es la misma que la del registrado en el sistema.'
                elif res_cai.company_id.id != invoice.company_id.id:
                    message = 'La compañia de la factura no es la misma que la del CAI registrado en el sistema.'

                # if message != '':
                #     raise ValidationError(_(message))
                if res_cai:
                    invoice_date = invoice.invoice_date
                    res_cai._validate_cai(invoice_date, int(sequence))

        return res_cai, message

    def _validate_cai(self, invoice_date, sequence):
        if not invoice_date:
            raise ValidationError(_("Asegúrse de asignar una fecha al comprobante."))
        date_start = self.date_start
        date_end = self.date_end
        limit_init = self.limit_init
        limit_end = self.limit_end

        if invoice_date > date_end:
            raise ValidationError(_("La fecha límite de este C.A.I es %s , mientras que la fecha de la factura es %s" % (date_end, invoice_date)))
        if invoice_date < date_start:
            raise ValidationError(_("La fecha de inicio de este C.A.I es %s , mientras que la fecha de la factura es %s" % (date_start, invoice_date)))
        if int(sequence) > limit_end:
            raise ValidationError(_("Al validar este comprobante generará la secuencia %s, sin embargo el rango máximo de este C.A.I es %s " % (sequence, limit_end)))
        if int(sequence) < limit_init:
            raise ValidationError(_("Al validar este comprobante generará la secuencia %s, sin embargo el rango mínimo de este C.A.I es %s " % (sequence, limit_init)))

    def _cai_validate_customer(self, invoice):

        journal_id = invoice.journal_id
        cai_ids = journal_id.cai_ids
        invoice_date = invoice.invoice_date or datetime.now().date()
        document_type_id = invoice.document_type_sale_id
        cai_id = False
        if cai_ids:
            cai_id = cai_ids.filtered(lambda c: c.date_start <= invoice_date <= c.date_end and c.document_type_id.id == document_type_id.id
                             and c.type_use == 'sale')
        if cai_id:
            return cai_id, False
        else:
            return cai_id, "CAI no encontrado. Verifique los parámetros de búsqueda, o cree un cai."

    @api.depends('terminal_id','sucursal_id','document_type_id','sequence_id','sequence_range_id')
    def _compute_next_cai_number(self):
        for record in self:
            next_cai_number = False
            if record.terminal_id and record.sucursal_id and record.document_type_id and record.sequence_id and record.sequence_range_id:
                terminal_code = record.terminal_id.code
                sucursal_code = record.sucursal_id.code
                document_code = record.document_type_id.code
                sequence_id = record.sequence_id
                padding = sequence_id.padding
                sequence_range_id = record.sequence_range_id
                next_number = str(sequence_range_id.number_next_actual)
                next_cai_number = '%s-%s-%s-%s' % (sucursal_code, terminal_code, document_code, next_number.zfill(padding))
            record.next_cai_number = next_cai_number