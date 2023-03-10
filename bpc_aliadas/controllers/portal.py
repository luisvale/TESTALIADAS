# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
import binascii

from odoo import http, _
from odoo.http import request
from odoo.osv.expression import AND, OR
from odoo.addons.portal.controllers.mail import _message_post_helper
from odoo import fields, http, SUPERUSER_ID, _
from odoo.exceptions import AccessError, MissingError, ValidationError

from odoo.addons.portal.controllers import portal
from odoo.addons.portal.controllers.portal import pager as portal_pager

class AliadasPortal(portal.CustomerPortal):

    @http.route(['/my/orders/<int:order_id>/accept'], type='json', auth="public", website=True)
    def portal_quote_accept(self, order_id, access_token=None, name=None, signature=None):
        # get from query string if not on json param
        access_token = access_token or request.httprequest.args.get('access_token')
        try:
            order_sudo = self._document_check_access('sale.order', order_id, access_token=access_token)
        except (AccessError, MissingError):
            return {'error': _('Invalid order.')}

        if not order_sudo.has_to_be_signed():
            return {'error': _('The order is not in a state requiring customer signature.')}
        if not signature:
            return {'error': _('Signature is missing.')}

        try:
            order_sudo.write({
                'signed_by': name,
                'signed_on': fields.Datetime.now(),
                'signature': signature,
                'accept_and_signed': True
            })
            request.env.cr.commit()
        except (TypeError, binascii.Error) as e:
            return {'error': _('Invalid signature data.')}

        if not order_sudo.has_to_be_paid():
            #order_sudo.action_confirm() NO CANCELAR
            order_sudo._send_order_confirmation_mail()

        pdf = request.env.ref('sale.action_report_saleorder').with_user(SUPERUSER_ID)._render_qweb_pdf([order_sudo.id])[0]

        _message_post_helper(
            'sale.order', order_sudo.id, _('Order signed by %s') % (name,),
            attachments=[('%s.pdf' % order_sudo.name, pdf)],
            **({'token': access_token} if access_token else {}))

        query_string = '&message=sign_ok'
        if order_sudo.has_to_be_paid(True):
            query_string += '#allow_payment=yes'
        return {
            'force_refresh': True,
            'redirect_url': order_sudo.get_portal_url(query_string=query_string),
        }

    # @http.route(['/my/orders/<int:order_id>/decline'], type='http', auth="public", methods=['POST'], website=True)
    # def decline(self, order_id, access_token=None, **post):
    #     try:
    #         order_sudo = self._document_check_access('sale.order', order_id, access_token=access_token)
    #     except (AccessError, MissingError):
    #         return request.redirect('/my')
    #
    #     message = post.get('decline_message')
    #
    #     query_string = False
    #     if order_sudo.has_to_be_signed() and message:
    #         #order_sudo.action_cancel() NO CANCELAR
    #         _message_post_helper('sale.order', order_id, message, **{'token': access_token} if access_token else {})
    #     else:
    #         query_string = "&message=cant_reject"
    #
    #     return request.redirect(order_sudo.get_portal_url(query_string=query_string))
