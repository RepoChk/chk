# coding: utf-8
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AccountJournal(models.Model):
    _inherit = 'account.journal'

    invoice_seq_id = fields.Many2one(
        'ir.sequence', 
        string='Nro Documento',
        help="Este campo asigna el nro a un documento sea factura, NC, ND", 
        copy=False,
        tracking=True,
    )

    invoice_ctrl_seq_id = fields.Many2one(
        'ir.sequence', 
        string='Nro Control', 
        help="Este campo asigna el nro de control de un documento sea factura, NC, ND", 
        copy=False,
        tracking=True,
    )

    branch_id = fields.Many2one('res.company', string='Sucursal', domain="[('parent_id', '=', company_id)]", tracking=True,)
    invoice_seq_number_next = fields.Char(compute='_compute_next_seq')
    ctrl_seq_number_next = fields.Char(compute='_compute_next_seq')

    exclude_fiscal_documents = fields.Boolean(
        string='Excluir documentos publicados del libro fiscal',
        help="Si está habilitado, las facturas publicadas se marcarán automáticamente como excluidas del libro fiscal."
    )

    gc_payment_method = fields.Many2many(
        'gc.account.payment.method',
        string='Metodos de Pago',
    )
    
    @api.depends('invoice_seq_id','invoice_ctrl_seq_id')
    def _compute_next_seq(self):
        for rec in self:
            rec.invoice_seq_number_next=rec.invoice_seq_id.number_next_actual
            rec.ctrl_seq_number_next=rec.invoice_ctrl_seq_id.number_next_actual