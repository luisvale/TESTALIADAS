from odoo import models, api, _, fields
from odoo.exceptions import ValidationError, UserError

LEN = 3

class CompanySucursal(models.Model):
    _name = 'company.sucursal'
    _description = 'Sucursal'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
    _rec_name = 'code'

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    code = fields.Char(string=u'Código', required=True)
    description = fields.Char(string=u'Descripción')

    _sql_constraints = [
        ('name_sucursal_uid_unique', 'unique (code, company_id)', 'Solo puede existir una sucursal por compañía con este código'),
    ]

    @api.onchange('code')
    def _onchange_code(self):
        for record in self:
            if record.code and len(record.code) < LEN:
                code = record.code
                record.code = code.zfill(LEN)