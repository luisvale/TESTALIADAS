# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, date


class ResPartner(models.Model):
    _inherit = 'res.partner'

    check_cai = fields.Boolean(string='Validar C.A.I')

    cai_id = fields.Many2one('res.cai', string='C.A.I.(Activo)', compute='_compute_cai_id')
    lines_cai_ids = fields.Many2many('res.cai', string='Lista de C.A.I')

    @api.depends('lines_cai_ids')
    def _compute_cai_id(self):
        for record in self:
            cai_id = False
            if record.lines_cai_ids:
                cai_id = record._cai_active()

            record.cai_id = cai_id


    def _cai_active(self):
        cai_id = False
        self.ensure_one()
        now = date.today()
        if self.lines_cai_ids:
            #Búsqueda por fechas
            cai_ids = self.lines_cai_ids.filtered(lambda l: l.date_start <= now and l.date_end >= now and l.partner_id == self.ids[0])
            if not cai_id:
                cai_first = self.lines_cai_ids[0]
                for line in self.lines_cai_ids:
                    if line.date_end > cai_first.date_end:
                        cai_id = line
                    else:
                        cai_id = cai_first
            elif len(cai_ids.ids) > 0:
                cai_id = cai_ids[0]
            else:
                pass

        return cai_id





