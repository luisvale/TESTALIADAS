
def get_data(self, param):
    if param == 'area':
        return area(self)
    elif param == 'rent_ok':
        return rent_ok(self)
    elif param == 'recurring_ok':
        return recurring_ok(self)
    elif param == 'others':
        return others(self)
    elif param == 'no_total':
        return no_total(self)


def area(self):
    product_rental_id = self.env.ref('bpc_aliadas.rental_product_bpc')
    total_area = sum(line.product_uom_qty if line.product_id.rent_ok and line.product_id.id != product_rental_id.id else 0.0 for line in self.order_line)
    return total_area


def rent_ok(self):
    return self.order_line.filtered(lambda l: l.product_id.rent_ok)


def recurring_ok(self):
    return self.order_line.filtered(lambda l: l.product_id.recurring_invoice and not l.product_id.rent_ok)


def others(self):
    return self.order_line.filtered(lambda l: not l.product_id.recurring_invoice and not l.product_id.rent_ok and not l.product_id.not_total)


def no_total(self):
    return self.order_line.filtered(lambda l: l.product_id.not_total)