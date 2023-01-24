from odoo import models, api, _, fields
from odoo.exceptions import ValidationError, UserError
from datetime import date, datetime
import logging

_logger = logging.getLogger(__name__)

USED = [('sale', 'Ventas'), ('purchase', 'Compras')]
STATE = [('draft', 'Inactivo'), ('done', 'Activo')]


class ResCaiTrigger(models.Model):
    _name = 'res.cai.trigger'
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

    def name_get(self):
        result = []
        for record in self:
            if record.type_use == 'purchase':
                result.append((record.id, '%s / %s' % (record.partner_id.name, record.cai)))
            else:
                result.append((record.id, '%s / %s' % (record.company_id.name, record.cai)))
        return result

    @api.model
    def _create_mirror(self, invoice, cai_origin):

        if invoice.move_type not in ('in_invoice', 'in_refund'):
            return False

        if invoice.move_type in ('in_invoice', 'in_refund'):
            data = {
                'company_id': cai_origin.company_id.id,
                'type_use': cai_origin.type_use,
                'cai': cai_origin.cai,
                'range_start': cai_origin.range_start,
                'range_end': cai_origin.range_end,
                'limit_init': cai_origin.limit_init,
                'limit_end': cai_origin.limit_end,
                'date_start': cai_origin.date_start,
                'date_end': cai_origin.date_end,
                'partner_id': cai_origin.partner_id.id,
                'state': cai_origin.state,
                'terminal_code': cai_origin.terminal_code,
                'sucursal_code': cai_origin.sucursal_code,
                'document_type_id': cai_origin.document_type_id.id,
                'journal_id': cai_origin.journal_id.id,
            }

            cai_mirror = self.env['res.cai.trigger'].sudo().search([('partner_id', '=', cai_origin.partner_id.id),
                                                                  ('type_use', '=', 'purchase'),
                                                                  ('cai', '=', cai_origin.cai),
                                                                  ('range_start', '=', cai_origin.range_start),
                                                                  ('range_end', '=', cai_origin.range_end),
                                                                  ('terminal_code', '=', cai_origin.terminal_code),
                                                                  ('sucursal_code', '=', cai_origin.sucursal_code),
                                                                  ('document_type_id', '=', cai_origin.document_type_id.id),
                                                                  ('journal_id', '=', cai_origin.journal_id.id),
                                                                  ], limit=1)
            if not cai_mirror:
                cai_mirror = self.env['res.cai.trigger'].sudo().create(data)
                message_body = ""
                message_body += ("<p><b>ID CAI ORIGEN: </b> {}</p>".format(cai_origin.id))
                cai_mirror.message_post(body=message_body, subtype_xmlid="mail.mt_note", message_type='comment')

            if cai_mirror:
                _logger.info("CAI ESPEJO creado con ID %s " % cai_mirror.id)
            return cai_mirror

        return False

        ##SEQUENCE ??
