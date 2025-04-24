# coding: utf-8
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class HrDiscount(models.Model):
    _name = 'hr.discount'
    _description = 'Descuentos en Nómina'

    name = fields.Char(
        string='Nombre', 
        readonly=True, 
    )

    payslip_id = fields.Many2one(
        'hr.payslip',
        string='Recibo de nómina',
    )

    payslip_run_id = fields.Many2one(
        'hr.payslip.run',
        related='payslip_id.payslip_run_id',
        string='Lote',
        store=True,
    )

    company_id = fields.Many2one(
        'res.company', 
        default=lambda self: self.env.company,
        string='Compañía',
    )

    currency_id_dif = fields.Many2one(
        "res.currency",
        string="Divisa de Referencia",
        default=lambda self: self.env.company.currency_id_dif,
    )

    currency_id_company = fields.Many2one(
        "res.currency",
        string="Divisa compañia",
        default=lambda self: self.env.company.currency_id,
    )

    employee_id = fields.Many2one(
        'hr.employee', 
        string='Empleado', 
        store=True,
    )

    discount_type_id = fields.Many2one(
        'hr.discount.type', 
        string='Tipo descuento',
    )

    amount_usd = fields.Monetary(
        string='Monto USD', 
        currency_field='currency_id_dif',
    )

    amount_bs = fields.Monetary(
        string='Monto', 
        currency_field='currency_id_company',
        compute='_compute_amount_bs',
        store=True,
    )

    rate = fields.Float(
        string='Tasa de Cambio', 
        required=True, 
        default=1, 
        digits='Dual_Currency_rate', 
    )

    # FECHA ACTUAL
    date_from = fields.Date(
        string='Fecha', 
        required=True, 
        default=lambda self: fields.Date.context_today(self), 
        readonly=True, 
    )

    # FECHA DE COBRO
    date_to = fields.Date(
        string='Fecha Cobro', 
        default=lambda self: fields.Date.context_today(self),
    )

    struct_id = fields.Many2one(
        'hr.payroll.structure',
        string='Estructura',
    )

    @api.depends('amount_usd')
    def _compute_amount_bs(self):
        for rec in self:
            rate = 1
            if rec.payslip_id:
                rate = rec.payslip_id.tasa_cambio
            rec.amount_bs = rec.amount_usd * rate if rec.amount_usd > 0 else 0

    def unlink(self):
        for rec in self:
            if rec.payslip_id.state in ('done', 'paid'):
                raise UserError(_('No se puede eliminar un descuento de un recibo de nómina en estatus Listo o Pagado.'))
        return super(HrDiscount, self).unlink()

