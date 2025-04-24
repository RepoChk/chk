# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class GCHrEmployeeLoanType(models.Model):
    _name = 'gc.hr.employee.loan.type'
    _description = 'Tipo de Préstamo de Empleado'

    name = fields.Char('Nombre', required=True)
    struct_id = fields.Many2one('hr.payroll.structure', 'Estructura', required=True)
    rule_id = fields.Many2one('hr.salary.rule', 'Regla de Nómina', required=True)
    account_id = fields.Many2one('account.account', 'Cuenta Contable', required=True, related='rule_id.account_credit', store=True,)
    company_id = fields.Many2one('res.company', 'Compañía', default=lambda self: self.env.company)
    active = fields.Boolean('Activo', default=True)
    note = fields.Text('Notas')

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'El nombre del tipo de prestamo debe ser unico!'),
    ]