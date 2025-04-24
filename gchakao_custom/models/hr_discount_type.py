# coding: utf-8
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class HrDiscountType(models.Model):
    _name = 'hr.discount.type'
    _description = 'Tipos de descuentos de nomina'

    name = fields.Char(
        string='Nombre',
    )

    code = fields.Char(
        string='Código',
        size=4
    )