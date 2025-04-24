# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.tools import ustr
from odoo.exceptions import UserError


class ApplyCreditNoteWizard(models.TransientModel):
    _name = 'apply.credit.note.wizard'
    _description = 'Aplicar nota de credito'

    company_id = fields.Many2one(
        'res.company', 
        string='Compañía', 
        default=lambda self: self.env.company, 
        required=True, 
        readonly=True,
    )

    journal_id = fields.Many2one(
        'account.journal',
        string='Diario',
        domain=[('type','=','sale')],
        required=True,
    )

    def action_generate_cn(self):
        self.ensure_one()
        values = self.env.context.get('default_refund_values', {})
        if self.journal_id:
            values['journal_id'] = self.journal_id.id
        
        # Creamos la nota de crédito
        credit_note = self.env['account.move'].create(values)
        
        # Actualizamos la garantía con la referencia a la nota de crédito
        credit_note.warranty_id.write({'nc_id': credit_note.id})
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Nota de Crédito',
            'res_model': 'account.move',
            'res_id': credit_note.id,
            'view_mode': 'form',
            'view_type': 'form',
        }
