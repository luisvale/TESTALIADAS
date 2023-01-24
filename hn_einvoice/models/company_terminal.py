from odoo import models, api, _, fields
from odoo.exceptions import ValidationError, UserError

LEN = 3

class CompanyTerminal(models.Model):
    _name = 'company.terminal'
    _description = 'Terminal'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    code = fields.Char(string=u'Código', required=True)
    description = fields.Char(string=u'Descripción')
    sucursal_id = fields.Many2one('company.sucursal', string='Sucursal', required=True)
    company_id = fields.Many2one('res.company', related='sucursal_id.company_id', store=True, readonly=False)


    _sql_constraints = [
        ('name_terminal_uid_unique', 'unique (code, sucursal_id, company_id)', 'Solo puede existir una terminal para la sucursal de esta compañía con este código'),
    ]

    @api.onchange('code')
    def _onchange_code(self):
        for record in self:
            if record.code and len(record.code) < LEN:
                code = record.code
                record.code = code.zfill(LEN)


    def name_get(self):
        result = []
        for record in self:
            result.append((record.id, '%s / Sucursal: %s' % (record.code, record.sucursal_id.code)))
        return result