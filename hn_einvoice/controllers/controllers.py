# -*- coding: utf-8 -*-
# from odoo import http


# class HnEinvoice(http.Controller):
#     @http.route('/hn_einvoice/hn_einvoice', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/hn_einvoice/hn_einvoice/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('hn_einvoice.listing', {
#             'root': '/hn_einvoice/hn_einvoice',
#             'objects': http.request.env['hn_einvoice.hn_einvoice'].search([]),
#         })

#     @http.route('/hn_einvoice/hn_einvoice/objects/<model("hn_einvoice.hn_einvoice"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('hn_einvoice.object', {
#             'object': obj
#         })
