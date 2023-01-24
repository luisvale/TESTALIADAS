# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountMoveReversal(models.TransientModel):
    _inherit = "account.move.reversal"


    def _prepare_default_reversal(self, move):
        res = super(AccountMoveReversal, self)._prepare_default_reversal(move)

        document_type_id = self.env.ref('hn_einvoice.document_nota_credito').id
        #res['journal_id'] = move.journal_id.id
        if move.document_type_sale_id:
            res['document_type_sale_id'] = document_type_id
        elif move.document_type_purchase_id:
            res['document_type_purchase_id'] = document_type_id
        res['document_type_id'] = document_type_id if move.document_type_id else False
        res['move_o_ids'] = [(6, 0, move.ids)]
        res['check_cai'] = move.check_cai,
        res['cai_id'] = False

        #invoice_date = res['invoice_date']

        return res


