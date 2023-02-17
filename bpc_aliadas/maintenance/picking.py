import logging

_logger = logging.getLogger(__name__)


def _eval_products(self, process_qty_news=False):
    #lines_with_stock = self.material_line_ids.filtered(lambda l: l.stock > 0.0 and l.stock >= l.quantity)
    if not process_qty_news:
        lines_with_stock = self.material_line_ids.filtered(lambda l: l.stock > 0.0 and l.stock >= l.quantity)
    else:
        lines_with_stock = self.material_line_ids.filtered(lambda l: l.stock > 0.0 and l.stock >= l.quantity_add and l.quantity_add > 0.0)
    if lines_with_stock:
        res, error = _create_picking(self, lines_with_stock, process_qty_news)
        return res, error
    else:
        return False, "No hay líneas con stock disponible o la disponibilidad no equivale a la cantidad solicitada."


def _create_picking(self, lines, process_qty_news):
    # create picking output to trigger creating MO for reordering product_1

    def _get_lines(lines):
        lines_list = []
        for l in lines:
            product = l.product_id.product_variant_id
            lines_list.append((0, 0, {
                'name': '/',
                'product_id': product.id,
                'product_uom': product.uom_id.id,
                'product_uom_qty': l.quantity if not process_qty_news else l.quantity_add,
                'procure_method': 'make_to_stock',
                'location_id': self.location_init_id.id,
                'location_dest_id': self.location_end_id.id,
            }))
            if process_qty_news:
                l.sudo().write({'quantity_add': 0.0})

        return lines_list

    if process_qty_news:
        lines = lines.filtered(lambda l: l.quantity_add > 0)
    move_lines = _get_lines(lines)
    try:
        data = {
                'name': '/',
                'picking_type_id': self.env.ref('stock.picking_type_out').id,
                'location_id': self.location_init_id.id,
                'location_dest_id': self.location_end_id.id,
                'move_lines': move_lines,
                'origin': self.name,
                'maintenance_id': self.ids[0]
            }
        if not self.picking_id and not process_qty_news:
            pick_output = self.env['stock.picking'].sudo().create(data)
            self.picking_id = pick_output
            return True, ''

        elif process_qty_news:
            pick_output = self.env['stock.picking'].sudo().create(data)
            self.picking_ids += self.picking_id
            self.picking_ids += pick_output
            return True, ''
        else:
            return True, ''

    except Exception as e:
        _logger.info("ALIADAS: Mantenimiento, creación de picking con error :%s" % e)
        return False, e
