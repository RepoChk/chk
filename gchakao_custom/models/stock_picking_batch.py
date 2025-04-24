# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

    vehicle_id = fields.Many2one(
        'fleet.vehicle', string='Vehículo', tracking=True
    )
    driver_id = fields.Many2one(
        'res.partner', string='Conductor'
    )
    vehicle_filler = fields.Float(
        string='Filler del Vehículo', related='vehicle_id.vehicle_filler', store=True,
    )
    loaded_filler = fields.Float(
        string='Filler Cargado', compute="_calculate_loaded_filler", store=True
    )
    date_end = fields.Datetime(
        string='Fecha Hasta',
    )
    delivery_date = fields.Datetime(
        'Fecha de Llegada',
        tracking=True
    )
    type_vehicle = fields.Selection(
        [('internal', 'Interno'), ('external', 'Externo')], related='vehicle_id.type_vehicle', string='Tipo de Vehículo'
    )
    km_estimate = fields.Float(
        string='Kilómetros Estimados', tracking=True
    )
    disel_consumed = fields.Float(
        string='Consumo de Gasoil', tracking=True
    )
    coste_km = fields.Float(
        string='Costo por Kilómetro', tracking=True
    )


    @api.onchange('vehicle_id')
    def _onchange_driver(self):
        for rec in self:
            rec.driver_id = rec.vehicle_id.driver_id

    
    @api.depends('picking_ids','vehicle_filler')
    def _calculate_loaded_filler(self):
        for rec in self:
            fillert = 0
            if len(rec.picking_ids) > 0:
                for picking in rec.picking_ids:
                    for line in picking.move_ids_without_package:
                        if line.filler:
                            cantidad = line.product_uom_qty * line.filler if line.product_uom_qty > 0 else line.quantity * line.filler
                            fillert += cantidad
            rec.loaded_filler = fillert

    def action_confirm(self):
        if self.loaded_filler > self.vehicle_filler:
            raise ValidationError(f'El cargamento excede la cantidad máxima de filler del vehículo.\nFiller del vehículo: {self.vehicle_filler:.2f}\nFiller Cargado: {self.loaded_filler:.2f}')
        else: 
            self.state = 'in_progress'

    def get_responsible(self):
        return self.env['res.users'].search([('id', '=', self.env.uid)]).name
    
    def get_zones(self):
        zones = []
        result = ''
        for picking in self.picking_ids:
            zones += [picking.city]
        z_len = len(set(zones))
        for zone in set(zones):
            if zone:
                result += zone
                if z_len > 1:
                    result += ', '
            z_len -= 1
        return result

    def get_qty_clients(self):
        clients = []
        result = ''
        for picking in self.picking_ids:
            clients += [picking.partner_id]
        result = len(set(clients))
        return result
    
    def get_qty_products(self):
        product_qty = 0
        for picking in self.picking_ids:
            for line in picking.move_ids_without_package:
                if line.quantity > 0:
                    product_qty += line.quantity
                else:
                    product_qty += line.product_uom_qty
        return product_qty