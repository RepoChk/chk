# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class ResPartner(models.Model):
    _inherit = 'res.partner'

    sub_provider_ids = fields.Many2many(
        'res.partner','sub_provider_rel','partner_id','provider_id', string=' Sub Provider', tracking=True
    )
    location_client = fields.Char(
        string='Ubicación del Cliente (Link)', tracking=True
    )
    key_account = fields.Boolean(
        string='Cuenta Clave', tracking=True
    )
    client_creation_sheet = fields.Boolean(
        string='Planilla de creación de cliente', tracking=True
    )
    commercial_registry = fields.Boolean(
        string='Registro Mercantil', tracking=True
    )
    constitutive_act = fields.Boolean(
        string='Acta Constitutiva', tracking=True
    )
    updated_constitutive_act  = fields.Boolean(
        string='Actualización de Acta Constitutiva', tracking=True
    )
    copy_document_legal_representative = fields.Boolean(
        string='Copia de CI del Representante Legal', tracking=True
    )
    updated_rif = fields.Boolean(
        string='RIF Actualizado' , tracking=True
    )
    customer_group_id = fields.Many2many(
        'customer.group', 
        string='Grupo de Clientes', 
        tracking=True
    )
    
    customer_segmentation = fields.Selection([
        ('a', 'A'),
        ('b', 'B'),
        ('c', 'C'),
        ('d', 'D'),
        ('z', 'Z'),
    ], string='Segmentación del Cliente', tracking=True)

    customer_type = fields.Selection([
        ('asociaciones_agremiadas', 'Asociaciones Agremiadas'),
        ('consumidor_final', 'Consumidor Final'),
        ('distribuidor', 'Distribuidor'),
        ('distribuidor_eventual', 'Distribuidor Eventual'),
        ('flota', 'Flota'),
        ('otras_entidades', 'Otras Entidades')
    ], string='Tipo de Cliente', tracking=True)

    function = fields.Char(
        string='Puesto de Trabajo', store=True
    )

    identification_document = fields.Char(
        string='Documento de Identificación'
    )

    legal_representative = fields.Many2one(
        'res.partner',
        string='Representante Legal',
        domain="[('id', 'in', allowed_legal_representatives)]",
        tracking=True
    )

    allowed_legal_representatives = fields.Many2many(
        'res.partner',
        compute='_compute_allowed_legal_representatives',
        store=False
    )

    credit_limit = fields.Monetary(
        default=0, 
        string='Límite de Crédito',
        tracking=True, 
        currency_field='currency_id_dif', 
    )

    available_credit = fields.Monetary(
        string='Crédito Disponible', 
        default=0, 
        compute='_compute_available_credit', 
        currency_field='currency_id_dif', 
    )

    cuenta_anticipo_proveedores_id = fields.Many2one('account.account', string='Cuenta Anticipo Proveedores',
                                                        help='Cuenta contable para los anticipos de proveedores', company_dependent=True)

    cuenta_anticipo_clientes_id = fields.Many2one('account.account', string='Cuenta Anticipo Clientes',
                                                        help='Cuenta contable para los anticipos de clientes', company_dependent=True)

    @api.depends('credit_limit', 'invoice_ids.state', 'invoice_ids.amount_residual', 'invoice_ids.currency_id')
    def _compute_available_credit(self):
        for partner in self:
            total_used_credit = 0
            for invoice in partner.invoice_ids.filtered(lambda inv: inv.state == 'posted'):
                if invoice.currency_id.id == invoice.company_id.currency_id_dif.id:
                    total_used_credit += invoice.amount_residual_usd
                else:
                    total_used_credit += invoice.amount_residual_usd * invoice.currency_id.rate
            partner.available_credit = partner.credit_limit - total_used_credit

    @api.model
    def _get_customer_groups(self):
        groups = self.env['customer.group'].search([])
        return [(str(group.id), group.name) for group in groups]

    
