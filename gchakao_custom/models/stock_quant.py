# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

class StockQuant(models.Model):
    _inherit = "stock.quant"

    tracking_number = fields.Char(
        related='lot_id.tracking_number',
        string='Número de Seguimiento',
        store=True,
    )