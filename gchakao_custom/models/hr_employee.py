# -*- coding: utf-8 -*-

from odoo import models, fields,api

class HREmpleyee(models.Model):
    _inherit = 'hr.employee'

    identification_id = fields.Char(string="Cédula de Identidad", related='work_contact_id.identification_id', readonly=False, store=True,)
    nationality = fields.Selection([
        ('V', 'Venezolano'),
        ('E', 'Extranjero'),
        ('P', 'Pasaporte')], string="Tipo Documento", related="work_contact_id.nationality", readonly=False, store=True,)
    rif = fields.Char(string="RIF", related='work_contact_id.rif', readonly=False, store=True,)