# coding: utf-8
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class HrPayrollStructure(models.Model):
    _inherit = 'hr.payroll.structure'

    hr_payment_type = fields.Selection([
        ('nomina', 'Nómina'),
        ('complemento', 'Complemento'),
        ('indicador', 'Indicador'),
        ('cesta_ticket', 'Cesta Ticket'),
        ('commision', 'Comisiones'),
        ('vacation', 'Vacaciones'),
        ], 
        string="Tipo de Pago", 
        default='nomina', 
        required=True,
    )

    confidential = fields.Boolean(string="Confidencial")

    employee_ids = fields.One2many(
        'hr.payroll.employee',
        'structure_id',
        string='Empleados'
    )

    assigned_employees = fields.Many2many(
        'hr.employee',
        compute='_compute_assigned_employees',
    )

    @api.depends('employee_ids')
    def _compute_assigned_employees(self):
        for rec in self:
            rec.assigned_employees = rec.employee_ids.mapped('employee_id').ids