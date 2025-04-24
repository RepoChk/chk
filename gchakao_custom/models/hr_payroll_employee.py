# coding: utf-8
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class HrPayrollEmployee(models.Model):
    _name = 'hr.payroll.employee'
    _description = 'Empleados en las estructuras de nómina'
    _check_company_auto = True

    name = fields.Char(compute='_compute_name', store=True, string="Nombre")
    structure_id = fields.Many2one('hr.payroll.structure', string='Nómina', required=True, ondelete='cascade', company_dependent=True,)
    employee_id = fields.Many2one('hr.employee', string="Empleado", required=True, company_dependent=True,)
    company_id = fields.Many2one('res.company', string="Compañía", default=lambda self: self.env.company, required=True)

    @api.depends('employee_id')
    def _compute_name(self):
        for rec in self:
            rec.name = rec.employee_id.name if rec.employee_id else ''

    @api.constrains('employee_id', 'structure_id', 'company_id')
    def _check_unique_employee_structure(self):
        for record in self:
            if not record.employee_id or not record.structure_id or not record.company_id:
                continue
                
            duplicate = self.env['hr.payroll.employee'].search([
                ('employee_id', '=', record.employee_id.id),
                ('structure_id', '=', record.structure_id.id),
                ('company_id', '=', record.company_id.id),
                ('id', '!=', record.id)
            ], limit=1)
            
            if duplicate:
                raise ValidationError(_(
                    'El empleado %(employee)s ya está asignado a la estructura de nómina %(structure)s en la compañía %(company)s') % {
                        'employee': record.employee_id.name,
                        'structure': record.structure_id.name,
                        'company': record.company_id.name
                    })

    @api.model
    def create(self, vals):
        if 'employee_id' in vals and 'structure_id' in vals and 'company_id' in vals:
            duplicate = self.env['hr.payroll.employee'].search([
                ('employee_id', '=', vals['employee_id']),
                ('structure_id', '=', vals['structure_id']),
                ('company_id', '=', vals['company_id'])
            ], limit=1)
            
            if duplicate:
                employee = self.env['hr.employee'].browse(vals['employee_id'])
                structure = self.env['hr.payroll.structure'].browse(vals['structure_id'])
                company = self.env['res.company'].browse(vals['company_id'])
                raise ValidationError(_(
                    'El empleado %(employee)s ya está asignado a la estructura de nómina %(structure)s en la compañía %(company)s') % {
                        'employee': employee.name,
                        'structure': structure.name,
                        'company': company.name
                    })
                    
        return super(HrPayrollEmployee, self).create(vals)

    def write(self, vals):
        result = super(HrPayrollEmployee, self).write(vals)
        self._check_unique_employee_structure()
        return result