# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import uuid
from werkzeug.urls import url_encode
from odoo import api, exceptions, fields, models, _


class MailActivity(models.AbstractModel):
    _inherit = "mail.activity"

    @api.model_create_multi
    def create(self, vals_list):
        activities = super(MailActivity, self).create(vals_list)
        for activity in activities:
            need_sudo = False
            try:  # in multicompany, reading the partner might break
                partner_id = activity.user_id.partner_id.id
            except exceptions.AccessError:
                need_sudo = True
                partner_id = activity.user_id.sudo().partner_id.id

            # send a notification to assigned user; in case of manually done activity also check
            # target has rights on document otherwise we prevent its creation. Automated activities
            # are checked since they are integrated into business flows that should not crash.
            if activity.user_id != self.env.user:
                if not activity.automated:
                    activity._check_access_assignation()
                if not self.env.context.get('mail_activity_quick_update', False):
                    if need_sudo:
                        activity.sudo().action_notify()
                    else:
                        activity.action_notify()

            self.env[activity.res_model].browse(activity.res_id).message_subscribe(partner_ids=[partner_id])
            #if activity.date_deadline <= fields.Date.today():
            self.env['bus.bus']._sendone(activity.user_id.partner_id, 'mail.activity/updated', {'activity_created': True})
        return activities
