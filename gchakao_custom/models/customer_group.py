# coding: utf-8
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

class CustomerGroup(models.Model):
    _name = 'customer.group'
    _description = 'Grupo de Clientes'
    
    name = fields.Char(string='Grupo', required=True, unique=True)
    active = fields.Boolean(string='Habilitado', default=True)
    
    # Moneda asociada
    currency_id_dif = fields.Many2one(
        'res.currency', 
        string='Moneda Diferente', 
        required=True,
        default=lambda self: self.env.company.currency_id
    )

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company
    )

    # Lista de Clientes asociados al grupo (no editable)
    customer_ids = fields.One2many(
        'res.partner', 
        'customer_group_id', 
        string='Clientes en el Grupo'
    )

    # Crédito total límite del grupo (suma de los límites de crédito de cada cliente)
    total_credit_limit = fields.Monetary(
        string='Crédito Total Límite del Grupo',
        compute='_compute_total_credit_limit',
        currency_field='currency_id_dif',
        store=True
    )

    # Crédito disponible total del grupo (suma de los créditos disponibles de cada cliente)
    available_credit_group = fields.Monetary(
        string='Crédito Disponible del Grupo', 
        compute='_compute_available_credit_group', 
        currency_field='currency_id_dif',
        store=True
    )

    # Diferencia entre el crédito total límite y el crédito disponible
    credit_difference = fields.Monetary(
        string='Crédito Utilizado del Grupo',
        compute='_compute_credit_difference',
        currency_field='currency_id_dif',
        store=True
    )

    @api.depends('customer_ids.credit_limit')
    def _compute_total_credit_limit(self):
        for group in self:
            group.total_credit_limit = sum(group.customer_ids.mapped('credit_limit'))

    @api.depends('customer_ids.available_credit')
    def _compute_available_credit_group(self):
        for group in self:
            group.available_credit_group = sum(group.customer_ids.mapped('available_credit'))

    @api.depends('total_credit_limit', 'available_credit_group')
    def _compute_credit_difference(self):
        for group in self:
            group.credit_difference = group.total_credit_limit - group.available_credit_group