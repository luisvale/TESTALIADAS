from odoo import api, fields, models


class ApprovalCategory(models.Model):
    _inherit = 'approval.category'

    approval_type = fields.Selection(selection_add=[('salary', 'Create salary attachment')])
