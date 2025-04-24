from odoo import api, fields, models, http, _
from odoo.exceptions import ValidationError, UserError
from datetime import date, datetime, timedelta

class EmpleadosWizard(models.TransientModel):
    _name = 'empleados.wizard'
    _description = 'Agregar empleados de forma masiva'

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    employee_ids = fields.Many2many('hr.employee', 
        string="Empleados", 
        domain="[('active','=',True),('contract_id.state','=','open'),('company_id', '=', company_id),('id', 'not in', assigned_employees)]",
    )

    assigned_employees = fields.Many2many(
        'hr.employee',
        'assigned_employees_wizard_rel',
        default=lambda self: self.env.context.get('assigned_employees')
    ) 

    def action_transferir(self):
        context = self.env.context.get('structure')
        obj_hr_payroll_employee = self.env['hr.payroll.employee'].with_company(self.company_id)
        
        for emp in self.employee_ids:
            try:
                values = {
                    'company_id': self.company_id.id,
                    'employee_id': emp.id,
                    'structure_id': context,
                }
                obj_hr_payroll_employee.create(values)
            except Exception as e:
                raise UserError(_('Error al agregar el empleado %s: %s') % (emp.name, str(e)))
                
        return True