# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

class StockLot(models.Model):
    _inherit = 'stock.lot'

    date_from = fields.Date(
        'Fecha de inicio', 
        index=True, 
        copy=False, 
        tracking=True
    )
    
    date_to = fields.Date(
        'Fecha fin', 
        copy=False, 
        tracking=True
    )

    warranty_active = fields.Boolean(
        string='Garantia activada',
        tracking=True,
        readonly=True, 
    )

    date_sale = fields.Date(string='Fecha de Venta', tracking=True, readonly=True, )
    date_warranty = fields.Date(string='Fecha de Activación', tracking=True, readonly=True, )
