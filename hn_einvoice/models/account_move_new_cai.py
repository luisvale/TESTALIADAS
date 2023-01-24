# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import date, datetime
import logging
_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    #cai_supplier_id
    check_cai = fields.Boolean(string='Validar CAI ?', compute='_compute_check_cai', store=True, readonly=False)
    cai_date_end = fields.Date(string='Vencimiento CAI', tracking=True, compute='_compute_cai_id')
    cai_id = fields.Many2one('res.cai', string='CAI', store=True, tracking=True, compute='_compute_cai_id')
    message = fields.Char(help='Mensaje a mostrar', store=True, tracking=True, compute='_compute_cai_id')
    error = fields.Boolean(help='Mostar mensaje',store=True, tracking=True, compute='_compute_cai_id')
    cai_supplier = fields.Char(string='CAI', help='CAI de proveedor a buscar')
    document_type_sale_id = fields.Many2one('document.type', domain=[('in_sale', '=', True)])
    document_type_purchase_id = fields.Many2one('document.type', domain=[('in_purchase', '=', True)])
    document_type_id = fields.Many2one('document.type', string='Tipo Documento', store=True, compute='_compute_document_type_id')
    move_o_ids = fields.Many2many('account.move', 'move_invoices_notes_rel', 'move_id', 'origin_id', string='Facturas relacionadas')
    next_cai_number = fields.Char(string='Próximo número', compute='_compute_next_cai_number')

    @api.model
    def _get_default_journal(self):
        move_type = self._context.get('default_move_type', 'entry')
        if move_type in self.get_sale_types(include_receipts=True):
            journal_types = ['sale']
        elif move_type in self.get_purchase_types(include_receipts=True):
            journal_types = ['purchase']
        else:
            journal_types = self._context.get('default_move_journal_types', ['general'])

        if self._context.get('default_journal_id'):
            journal = self.env['account.journal'].browse(self._context['default_journal_id'])

            if move_type != 'entry' and journal.type not in journal_types:
                raise UserError(_(
                    "Cannot create an invoice of type %(move_type)s with a journal having %(journal_type)s as type.",
                    move_type=move_type,
                    journal_type=journal.type,
                ))
        else:
            journal = self._search_default_journal(journal_types)

        if move_type in self.get_sale_types(include_receipts=True) and self.env.user.journal_id:
            journal = self.env.user.journal_id
        return journal

    # @api.model
    # def _domain_journal(self):
    #     if self.env.user.journal_ids:
    #         return [('id','in',self.env.user.journal_ids.ids)]
    #     else:
    #         return [('id', 'in', self.suitable_journal_ids.ids)]
    # 
    # journal_id = fields.Many2one('account.journal', string='Diario', required=True, states={'draft': [('readonly', False)]},
    #                              check_company=True, domain=_domain_journal, copy=False, default=_get_default_journal)

    journal_id = fields.Many2one('account.journal', string='Diario', required=True, states={'draft': [('readonly', False)]},
                                 check_company=True, domain="[('id', 'in', suitable_journal_ids)]", copy=False, default=_get_default_journal)

    exchange_rate = fields.Float(compute="_compute_exchange_rate", store=True, string="Tipo cambio")
    amount_text = fields.Char("Monto en letras", compute="_get_amount_text")


    @api.depends('document_type_sale_id', 'document_type_purchase_id')
    def _compute_document_type_id(self):
        for record in self:
            document_type_id = False
            if record.document_type_sale_id:
                document_type_id = record.document_type_sale_id
            elif record.document_type_purchase_id:
                document_type_id = record.document_type_purchase_id
            record.document_type_id = document_type_id

    @api.onchange('journal_id')
    def _onchange_journal(self):
        if self.journal_id and self.move_type in ('out_invoice','out_refund'):
            if self.journal_id.id not in self.env.user.journal_ids.ids:
                raise ValidationError(_("El usuario no tiene acceso al diario %s " % self.journal_id.name))
        super(AccountMove, self)._onchange_journal()

    @api.depends("invoice_date", "company_id", "currency_id")
    def _compute_exchange_rate(self):
        for record in self:
            company_currency_id = record.company_currency_id
            invoice_currency_id = record.currency_id
            record.exchange_rate = invoice_currency_id._convert(1, company_currency_id, record.company_id, record.invoice_date or date.today())

    @api.depends('amount_total')
    def _get_amount_text(self):
        for invoice in self:
            amount_text = invoice.company_currency_id.amount_to_text(abs(invoice.amount_total_signed))
            invoice.amount_text = amount_text


    @api.depends('partner_id')
    def _compute_check_cai(self):
        for record in self:
            check_cai = False
            if record.partner_id:
                check_cai = record.partner_id.check_cai
            if record.move_type in ('out_invoice', 'out_refund'):
                check_cai = True
            record.check_cai = check_cai

    @api.onchange('ref')
    def _onchange_ref(self):
        for record in self:
            if record.ref and record.move_type in ('in_invoice','in_refund'):
                sp = record.ref.split('-')
                if len(sp) == 4:
                    code = sp[2]
                    if code:
                        document_type = self.env['document.type'].sudo().search([('code','=',code)])
                        if document_type:
                            record.document_type_id = document_type



    def _post(self, soft=True):
        """Sobreescritura de método _POS() """
        self._journal_generate_temporary()
        response = super(AccountMove, self)._post(soft)
        self._create_sequence()  # Creación de xml al validar el comprobante
        return response

    def _create_sequence(self):
        for inv in self:
            if inv.move_type in ('out_invoice', 'out_refund') and inv.check_cai:
                if not inv.document_type_id:
                    raise ValidationError(_("Si tiene el check para validar C.A.I. debe seleccionar el tipo de documento."))
                cai_id = inv.cai_id
                if cai_id:
                    inv._cai_generate_temporary()
                    cai_code = inv._cai_generate(cai_id)
                    inv.name = cai_code
                    inv.payment_reference = cai_code

            elif inv.move_type in ('in_invoice', 'in_refund') and inv.check_cai:
                if not inv.document_type_id:
                    raise ValidationError(_("Si tiene el check para validar C.A.I. debe seleccionar el tipo de documento."))
                #inv._get_cai_supplier()
                inv._journal_generate_success()
            else:
                inv._journal_generate_success()

    def _cai_generate_temporary(self):
        cai = self.cai_id
        sequence_range_id = cai.sequence_range_id
        sequence_id = cai.sequence_id
        number = str(sequence_range_id.number_next_actual)
        padding = sequence_id.padding
        name_temporal = number.zfill(padding)
        _logger.info("FACTURACION - Validación de CAI con secuencia %s para la fecha %s " % (name_temporal, self.invoice_date))
        #Validacion de limites y fechas de CAI
        cai._validate_cai(self.invoice_date, name_temporal)


    def _cai_generate(self, cai):
        _logger.info("FACTURACION - Procedemos a generar el CAI")
        terminal_code = cai.terminal_id.code
        sucursal_code = cai.sucursal_id.code
        document_code = cai.document_type_id.code
        new_number = cai.sequence_id.sudo().next_by_id(self.invoice_date)

        # 000 - 001 - 01 - 00000101
        cai_code = '%s-%s-%s-%s' % (sucursal_code, terminal_code, document_code, new_number)
        _logger.info("FACTURACION - CAI generado %s" % cai_code)
        self.document_type_id = cai.document_type_id
        return cai_code


    def _get_cai_customer(self):
        if not self.invoice_date:
            raise ValidationError(_("Asegúrese que la factura tenga una fecha."))
        cai = self.cai_id
        sequence_id = cai.sequence_range_id
        next_number = int(sequence_id.number_next_actual)
        cai_id = cai._cai_validate_customer(self)
        self.cai_id = cai_id
        self.cai_date_end = cai_id.date_end
        self.sucursal_id = cai_id.sucursal_id
        self.terminal_id = cai_id.terminal_id
        self.cai_date_end = cai_id.date_end

    def _get_cai_supplier(self):
        cai_id = self.env['res.cai'].sudo()._cai_validate_supplier(self)
        if cai_id:
            self.cai_id = cai_id
            self.cai_date_end = cai_id.date_end
        else:
            raise ValidationError(_("No se encontró ningún CAI para este proveedor, evaluando el campo  * Referencia Factura * "))

    def _journal_generate_temporary(self):
        #self.name = '/'
        for record in self:
            if record.error:
                raise ValidationError(_("Hay un advertencia: %s" % record.message))
            # if record.move_type == 'entry':
            #     continue
            journal_id = record.journal_id
            name = '/'
            if journal_id:
                if record.move_type not in ('out_invoice', 'out_refund', 'in_invoice', 'in_refund'):
                    sequence_id = journal_id.sequence_id
                    if not sequence_id:
                        raise ValidationError(_("Asegúrese de tener una secuencia para el diario %s" % journal_id.name))
                    name = sequence_id.next_by_id()
                elif record.move_type in ('out_refund', 'in_refund'):
                    sequence_id = journal_id.sequence_return_id
                    if not sequence_id:
                        raise ValidationError(_("Asegúrese de tener una secuencia rectificativa para el diario %s" % journal_id.name))
                    name = record.env.ref('hn_einvoice.sequence_move_temporary').next_by_id()
                else:
                    if not record.check_cai and record.move_type in ('in_invoice', 'in_refund'):
                        if not journal_id.sequence_without_id:
                            raise ValidationError(_("Para el diario %s se necesita una secuencia sin CAI" % journal_id.name))
                        sequence_id = journal_id.sequence_without_id
                    else:
                        sequence_id = journal_id.sequence_id
                    if not sequence_id:
                        raise ValidationError(_("Asegúrese de tener una secuencia para el diario %s" % journal_id.name))

                    name = record.env.ref('hn_einvoice.sequence_move_temporary').next_by_id()

                #name_temporal = sequence_id.get_next_char(sequence_id.number_next_actual)
                # number = str(sequence_id.number_next_actual)
                # padding = sequence_id.padding
                # name_temporal = '%s%s' % (prefix, number.zfill(padding))
                _logger.info("MOVE - Generación de nombre temporal %s " % name)
                record.name = name

        #_logger.info("MOVE - Generación de nombre temporal.")

    def _journal_generate_success(self):
        journal_id = self.journal_id
        if self.move_type in ('out_refund', 'in_refund'):
            sequence_id = journal_id.sequence_return_id
        else:
            if not self.check_cai and self.move_type in ('in_invoice','in_refund'):
                if not journal_id.sequence_without_id:
                    raise ValidationError(_("Para el diario %s se necesita una secuencia sin CAI" % journal_id.name))
                sequence_id = journal_id.sequence_without_id
            else:
                sequence_id = journal_id.sequence_id
        name = sequence_id.next_by_id()
        self.name = name
        self.payment_reference = name
        _logger.info("MOVE - Generación de nombre correcto %s " % name)

    def view_cai_supplier(self):
        self.ensure_one()
        if self.cai_id and self.move_type in ('in_invoice','in_refund') and self.check_cai:
            view_id = self.env.ref('hn_einvoice.view_res_cai_supplier_form').id
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'res.cai',
                'res_id': self.cai_id.id,
                'view_ids':  [[view_id, 'form']],
                'view_mode': 'form',
                'view_id': view_id,
                'context': {'default_type_use': 'purchase'}
            }

    def action_debit(self):
        action = self.env["ir.actions.actions"]._for_xml_id("hn_einvoice.action_view_account_move_debit")
        if self.is_invoice():
            action['name'] = _('Nota Débito')
        return action

    @api.depends('document_type_id', 'journal_id', 'ref', 'check_cai','invoice_date','partner_id')
    def _compute_cai_id(self):
        for record in self:
            cai_id = False
            msg = False
            cai_date_end = False
            if record.check_cai and record:
                if record.state == 'draft':
                    _logger.info("ALIDAS: Buscando CAI..")
                    if record.move_type in ('out_invoice', 'out_refund'):
                        cai_id, msg = self.env['res.cai'].sudo()._cai_validate_customer(record)

                    elif record.move_type in ('in_invoice', 'in_refund'):
                        cai_id, msg = self.env['res.cai'].sudo()._cai_validate_supplier(record)
                        if cai_id:
                            record.document_type_purchase_id = cai_id.document_type_id
                    cai_date_end = cai_id.date_end if cai_id else False
                else:
                    _logger.info("ALIDAS: Ya tiene cai, no buscar..")
                    cai_id = record.cai_id
                    cai_date_end = record.cai_id.date_end
            _logger.info("ALIDAS: Búsqueda cai - %s" % str(msg))
            record.cai_id = cai_id
            record.cai_date_end = cai_date_end
            record.message = msg
            record.error = False if not msg else True


    @api.depends('cai_id')
    def _compute_next_cai_number(self):
        for record in self:
            next_cai_number = False
            if record.cai_id:
                cai = record.cai_id
                if record.move_type in ['out_invoice','out_refund']:
                    terminal_code = cai.terminal_id.code
                    sucursal_code = cai.sucursal_id.code
                    document_code = cai.document_type_id.code
                    sequence_id = cai.sequence_id
                    padding = sequence_id.padding
                    sequence_range_id = cai.sequence_range_id
                    next_number = str(sequence_range_id.number_next_actual)
                    next_cai_number = '%s-%s-%s-%s' % (sucursal_code, terminal_code, document_code, next_number.zfill(padding))
            record.next_cai_number = next_cai_number