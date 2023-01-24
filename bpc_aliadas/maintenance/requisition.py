from datetime import datetime, date
from collections import defaultdict
import logging
_logger = logging.getLogger(__name__)

def _eval_stock(self):
    self.material_line_ids._compute_stock()
    return self.material_line_ids.filtered(lambda l: l.stock == 0.0)

def _eval_stock_products(self):
    lines_without_stock = _eval_stock(self)
    if lines_without_stock:
        _logger.info("ALIADAS : %s lineas que pasarán a requisito de compra" % len(lines_without_stock.ids))
        res, msg = _create_requisition(self, lines_without_stock)
        return res, msg
    else:
        return True, ''


def _create_requisition(self, lines_without_stock):
    """Agrupar productos y crear licitacion"""
    company = self.company_id
    product_ids = self.env['product.product'].sudo()
    new_list = defaultdict(list)
    lines_to_requisition = []
    origins = self.name
    for line in lines_without_stock:
        tmpl_id = line.product_id
        product = tmpl_id.product_variant_id
        lines_old = self.env['purchase.requisition'].sudo()._find_requisition_by_product(product.id, company.id)
        requisition_ids = lines_old.mapped('requisition_id')
        if not lines_old:
            product_ids += product
            seller_ids = product.product_tmpl_id.seller_ids
            if seller_ids:
                # supplier_ids += seller_ids.mapped('name')
                for seller in seller_ids:
                    data = {
                        'name': product.name,
                        'product_id': product.id,
                        'product_qty': line.quantity,
                        'product_uom': line.uom_id.id,
                        'price_unit': seller.price,
                    }
                    new_list[seller.name.id].append((0, 0, data))
                    # new_list.append({'partner': seller.name, 'values': })
            lines_to_requisition.append((0,0,{
                'product_id': product.id,
                'product_qty': line.quantity,
                'price_unit': 1,
                'product_uom_id': line.uom_id.id
            }))
        elif not self.purchase_requisition_id and requisition_ids:
            self.sudo().write({'purchase_requisition_ids': [(6, 0, requisition_ids.ids)]})
            _logger.info("ALIADAS: El producto %s se encuentra en una licitación en proceso " % product.product_tmpl_id.name)
            return False, ''
        elif self.purchase_requisition_id:
            _logger.info("ALIADAS: El mantenimiento ya tiene una licitación %s " % self.purchase_requisition_id.name)
            return False, ''


    if new_list:
        _logger.info("ALIADAS: Creando licitación desde MASTER ")
        requisition_new = self.env['purchase.requisition'].sudo().with_company(company).create({
            'line_ids': lines_to_requisition,
            'user_id': self.user_id.id,
            'currency_id': self.currency_id.id,
            'ordering_date': datetime.now().date(),
            'automatic': True,
            'origin': origins,
        })
        if requisition_new:
            _logger.info("ALIADAS: Licitacón con ID %s creada" % requisition_new.id)

            error = False
            for partner_id, line_ids in new_list.items():
                try:
                    purchase_order = self.env['purchase.order'].create({
                        'partner_id': partner_id,
                        'requisition_id': requisition_new.id,
                        'order_line': line_ids
                    })
                    _logger.info("ALIADAS: Orden de compra creada ID %s" % purchase_order)
                except Exception as e:
                    _logger.info("ALIADAS: Error al crear orden de compra %s " % e)
                    error = True

            if error:
                requisition_new.sudo().unlink()
            else:
                requisition_new.sudo().action_in_progress()
                self.purchase_requisition_id = requisition_new
            return False, ''
        else:
            return False, 'No se generó correctamente la licitación, comunicarse con el administrador.'
    else:
        return False, 'Alguno de los productos no tiene proveedores para generar una licitación y orden de compra'