from odoo import models, api, _, fields
from odoo.exceptions import ValidationError, UserError

class DocumentType(models.Model):
    _name = 'document.type'
    _description = 'Tipo de documento'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence asc'

    sequence = fields.Integer(string='Secuencia')
    code = fields.Char(string='Código')
    name = fields.Char(string='Nombre')
    in_sale = fields.Boolean('En ventas')
    in_purchase = fields.Boolean('En compras')
    active = fields.Boolean(required=False, default=True, string='Activo')