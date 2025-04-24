# -*- encoding: utf-8 -*-

from odoo import models, fields, api

class ResCompany(models.Model):
    _inherit = 'res.company'

    por_discount_pp = fields.Float(string='% Descuento por prestamo', default=30)
    registration_date_IVSS = fields.Date(string='Fecha de inscripción')
    regime = fields.Char(string='Régimen')
    risk = fields.Char(string='Riesgo')