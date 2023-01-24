from odoo import fields, models

class PaymentMethod(models.Model):
    _name = "payment.method"
    _description = "Método de pago"

    active = fields.Boolean(default=True)
    sequence = fields.Char()
    name = fields.Char()
    notes = fields.Text()
