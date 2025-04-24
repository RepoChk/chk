# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    filler = fields.Float(
        string='Filler',
        related='product_id.filler',
        store=True
    )
    weight = fields.Float(
        string='Peso',
        related='product_id.weight',
        store=True
    )
    
    tracking_number = fields.Char(
        string='Número de Seguimiento',
    )

    dispatch_id = fields.Many2one(
        related='picking_id.dispatch_id', store=True
    )
    
    dispatch_status = fields.Char(
        string='Estado del Despacho',
    )

    @api.onchange('tracking_number')
    def _onchange_tracking_number(self):
        lot = self.env['stock.lot']
        for rec in self:
            if rec.product_id.is_battery and rec.tracking_number and rec.picking_id.picking_type_id.code == 'incoming':
                lot_id = lot.search([('tracking_number', '=', rec.tracking_number)], limit=1)
                if not lot_id:
                    raise UserError('El Nro de seguimiento ingresado no esta relacionado con un código interno (serial de batería)')
                rec.lot_id = lot_id

    @api.onchange('lot_id')
    def _onchange_lot_id(self):
        for rec in self:
            if rec.product_id.is_battery and rec.lot_id and rec.picking_id.picking_type_id.code == 'incoming':
                if not rec.lot_id.tracking_number:
                    raise UserError('Éste serial no esta relacionado a un nro de seguimiento físico de batería')
                rec.tracking_number = rec.lot_id.tracking_number