# -*- coding: utf-8

from odoo import models, fields

class MaintenanceRequest(models.Model):
    _inherit = 'maintenance.request'

    kilometer = fields.Integer(string="Kilometraje (KM)")
    maintenance_workers = fields.One2many('hr.employee', 'name', string="Técnicos")
