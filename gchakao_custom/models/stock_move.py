# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression

class StockMove(models.Model):
    _inherit = 'stock.move'

    dispatch_status = fields.Char(
        string='Estado del Despacho',
    )
    
    filler = fields.Float(
        string='Filler',
        related='product_id.filler',
        store=True,
    )

    weight = fields.Float(
        string='Peso',
        related='product_id.weight',
        store=True,
    )
    

    def _search_picking_for_assignation_domain(self):
        domain = super()._search_picking_for_assignation_domain()
        domain = expression.AND([domain, [('dispatch_id', '=', False)]])
        return domain

    def _action_cancel(self):
        res = super()._action_cancel()

        for picking in self.picking_id:
            # Remove the picking from the dispatch if the whole dispatch isn't cancelled.
            if picking.state == 'cancel' and picking.dispatch_id and any(p.state != 'cancel' for p in picking.dispatch_id.picking_ids):
                picking.dispatch_id = None
        return res