# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime, time

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProductClassification(models.Model):
    _name = "product.classification"
    _description = 'Clasificación de productos'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
    _rec_name = 'name'

    name = fields.Char(string='Nombre')
    active = fields.Boolean(default=True, string='Activo')

    _sql_constraints = [
        ('name_uniq', 'unique (name)', "El nombre de la clasificación ya existe!"),
    ]

