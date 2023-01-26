# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, date
import logging

_logger = logging.getLogger(__name__)


class ProjectTask(models.Model):
    _inherit = 'project.task'

    is_maintenance = fields.Boolean(related='helpdesk_ticket_id.is_maintenance')

    def action_fsm_validate(self):
        self.restriction_maintenance()
        super(ProjectTask, self).action_fsm_validate()

    def restriction_maintenance(self):
        files = self.env['ir.attachment'].sudo().search([('res_model', '=', 'project.task'),
                                                         ('res_id', 'in', self.ids),
                                                         ('company_id', '=', self.env.company.id)])
        if not files:
            raise ValidationError(_("Esta tarea debe contener al menos un archivo adjunto."))
