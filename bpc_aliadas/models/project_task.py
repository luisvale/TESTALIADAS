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
    sale_team_id = fields.Many2one('crm.team', related='helpdesk_ticket_id.sale_team_id')

    def action_fsm_validate(self):
        self.restriction_maintenance()
        super(ProjectTask, self).action_fsm_validate()

    def restriction_maintenance(self):
        files = self.env['ir.attachment'].sudo().search([('res_model', '=', 'project.task'),
                                                         ('res_id', 'in', self.ids),
                                                         ('company_id', '=', self.env.company.id)])
        if not files:
            raise ValidationError(_("Esta tarea debe contener al menos un archivo adjunto."))

    def action_fsm_create_quotation(self):
        view_form_id = self.env.ref('sale.view_order_form').id
        action = self.env["ir.actions.actions"]._for_xml_id("sale.action_quotations")

        action.update({
            'views': [(view_form_id, 'form')],
            'view_mode': 'form',
            'name': self.name,
            'context': {
                'fsm_mode': True,
                'form_view_initial_mode': 'edit',
                'default_partner_id': self.partner_id.id,
                'default_task_id': self.id,
                'default_company_id': self.company_id.id,
                'default_from_maintenance': self.is_maintenance,
                'default_team_id': self.sale_team_id.id if self.sale_team_id else False,
            },
        })
        return action
