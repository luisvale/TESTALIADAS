# -*- coding: utf-8 -*-

from odoo import models,fields,api
from odoo.exceptions import UserError, AccessError

class MassCancelTransferSale(models.Model):
	_name = 'mass.cancel.wizard'
	_description='Mass Cancel Wizard'

	mass_cancel = fields.Boolean(required=True)

	def on_click(self):
		sale_order=self.env["sale.order"].browse(self._context.get('active_ids',[]))
		if self.mass_cancel == False:
			raise UserError(('Please give permission by clicking the check-box to cancel selected sale order.'))


		sale_list=[]
		sale_string = ''
		flag = False
		if self.mass_cancel == True:
			for order in sale_order:
				if order.state != 'done':
					order.action_cancel()
					order.write({'state': 'cancel'})
					stock = self.env['stock.picking'].search([('origin', '=', order.name)])
					for res in stock:
						res.unlink()
				for pick in order.picking_ids:
					if pick.state == 'done' or order.state=="done" :
						if order.name not in sale_list:
							sale_list.append(order.name)
							sale_string=str(sale_list).strip('[]')
							flag = True
									
					if(flag == True):
						raise UserError(('Unable to cancel sale order as some receptions have already been done or locked.\n {}'.format(sale_string)))

class MassCancelTransferPurchase(models.Model):
	_name = 'mass.cancel.wizard.purchase'
	_description='Mass Cancel Wizard Purchase'

	mass_cancel_purchase = fields.Boolean(required=True)

	def on_click_purchase(self):
		purchase_order=self.env["purchase.order"].browse(self._context.get('active_ids',[]))

		if self.mass_cancel_purchase == False:
			raise UserError(('Please give permission by clicking the check-box to cancel selected purchase order.'))
		

		purchase_list=[] 
		purchase_string = ''
		flag = False

		for order in purchase_order:
			if order.state != 'done':
				order.button_cancel()
				order.write({'state': 'cancel'})
				stock = self.env['stock.picking'].search([('origin', '=', order.name)])
				for res in stock:
					res.unlink()
			elif order.state == "done":
				for order in purchase_order:
					for pick in order.picking_ids:
						if pick.state == 'done' or order.state == "done":
							purchase_list.append(order.name)
							purchase_string = str(purchase_list).strip('[]')
							flag = True
				if (flag == True):
					raise UserError(
						('Unable to cancel purchase order as some receptions have already been done or locked.'
						 '\n {}'.format(purchase_string)))

class MassCancelTransferInvoice(models.Model):
	_name = 'mass.cancel.wizard.invoice'
	_description='Mass Cancel Wizard Invoice'

	mass_cancel_invoice= fields.Boolean(required=True)

	def on_click_invoice(self):
		invoice_quot=self.env["account.move"].browse(self._context.get('active_ids',[]))

		if self.mass_cancel_invoice == False:
			raise UserError(('Please give permission by clicking the check-box to cancel selected Invoice.'))

		for invoices in invoice_quot:
			if invoices.state=="posted":
				raise UserError(('You Cannot cancel paid invoice..! \n Your paid invoice is/are:{}'.format(invoices.name)))
			elif invoices.state == 'draft':
				invoices.button_cancel()
				invoices.write({'state':'cancel'})
			elif invoices.state == "cancel":
				raise UserError(('You Cannot cancel Cancelled Invoices'))


		