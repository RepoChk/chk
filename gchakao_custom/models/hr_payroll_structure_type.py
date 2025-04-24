# coding: utf-8
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class HrPayrollStructureType(models.Model):
    _inherit = 'hr.payroll.structure.type'

    code = fields.Char(string="Código", required=True)
    is_commission = fields.Boolean(string="Nómina de Comisiones", help="Activar para las nóminas de comisiones")