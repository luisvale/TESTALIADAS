# -*- coding: utf-8 -*-
from collections import defaultdict
from lxml import etree
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, frozendict
import logging
_logger = logging.getLogger(__name__)


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    partner_ids = fields.Many2many(
        'res.partner', 'mail_compose_message_res_partner_rel',
        'wizard_id', 'partner_id', 'Additional Contacts',
        domain=[('type', '!=', 'private'), ('active','in',(True, False)), ('state','in', ('done','draft'))])

    partner_prospect_id = fields.Many2one('res.partner', domain=[('active','=', False), ('state','=', 'draft')])

    def get_mail_values(self, res_ids):
        res = super(MailComposeMessage, self).get_mail_values(res_ids)
        if type(res) == dict:
            for id, x in res.items():
                x['partner_ids'] += self.partner_prospect_id.ids
                a=1

        return res