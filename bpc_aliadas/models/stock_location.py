# -*- coding: utf-8 -*-
from functools import partial

from odoo import _, fields, models, api
from odoo.exceptions import ValidationError, UserError
import requests
from datetime import datetime, date
import re
import logging
_logger = logging.getLogger(__name__)

USE = [('origin','Ubicación origen'), ('destiny','Ubicación destino')]


class StockLocation(models.Model):
    _inherit = "stock.location"

    maintenance_use = fields.Selection(USE, string='Uso en mantenimiento')

