from odoo import api, fields, models
class ResCompany(models.Model):
    _inherit = "res.company"

    cancel_paid_invoice = fields.Boolean(string='Cancel Paid Invoice?')
