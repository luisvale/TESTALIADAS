# -*- coding: utf-8 -*-
from functools import partial

from odoo import _, fields, models, api
from odoo.exceptions import ValidationError, UserError
import requests
from datetime import datetime, date
import re
import logging
_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    maintenance_id = fields.Many2one('maintenance.periodic', string='Mantenimiento')

