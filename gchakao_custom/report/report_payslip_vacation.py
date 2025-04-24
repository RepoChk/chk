# -*- coding: utf-8 -*-

from odoo import models, _, fields, api
from odoo.exceptions import UserError


class ReportPayslipVacation(models.TransientModel):
    _name = 'report.payslip.vacation'
    _description = 'Reporte de Vacaciones (individual)'

    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True)
    struct_id = fields.Many2one('hr.payroll.structure', string='Estructura de Nómina', required=True)
    contract_id = fields.Many2one('hr.contract', string='Contrato', required=True)
    vacation_period = fields.Date(string='Periodo de Vacaciones', required=True)

    