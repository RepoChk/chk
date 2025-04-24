# -*- coding: utf-8
from odoo import models, fields, api, _

class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    type_vehicle = fields.Selection(
        [('internal', 'Interno'), ('external', 'Externo')], string='Tipo de Vehículo', tracking=True
    )
    vehicle_filler = fields.Float(
        string='Filler del Vehículo', digits=(12, 2), tracking=True
    )
    vehicle_weight = fields.Float(
        string='Capacidad de Peso', digits=(12, 2), tracking=True
    )
    currency_id_dif = fields.Many2one(
        "res.currency", related="company_id.currency_id_dif", store=True
    )
    coste_km = fields.Monetary(
        string='Costo por Kilómetro', currency_field='currency_id_dif', store=True, tracking=True
    )