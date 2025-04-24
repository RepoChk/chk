from odoo import models, fields, api, _, tools
from odoo.exceptions import UserError
from datetime import datetime, timedelta

import logging

_logger = logging.getLogger(__name__)

class IntercompanyTransfer(models.Model):
    _name ='intercompany.transfer'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Reference', default='Nuevo', copy=False)


    out_company_id = fields.Many2one('res.company', string='Compañía que envía' ,track_visibility='onchange')
    out_journal_id = fields.Many2one('account.journal',track_visibility='onchange')
    out_payment_type = fields.Selection([('outbound', 'Enviar Dinero'), ('inbound', 'Recibir Dinero'), ('transfer', 'Transferencia Interna')], default='outbound', string='Tipo de Pago')
    out_payment_method_id = fields.Many2one('account.payment.method', string='Método de Pago')
    out_destination_account_id  = fields.Many2one('account.account',string='Cuenta Transitoria',track_visibility='onchange')

    in_company_id = fields.Many2one('res.company', string='Recieving Company',track_visibility='onchange')
    in_journal_id = fields.Many2one('account.journal',track_visibility='onchange')
    in_payment_type = fields.Selection([('outbound', 'Enviar Dinero'), ('inbound', 'Recibir Dinero'), ('transfer', 'Transferencia Interna')], default='inbound', string='Tipo de Pago')
    in_payment_method_id = fields.Many2one('account.payment.method', string='Método de Pago')
    in_destination_account_id  = fields.Many2one('account.account',string='Cuenta Transitoria',track_visibility='onchange')

    amount = fields.Monetary(string='Monto',track_visibility='onchange')
    currency_id = fields.Many2one('res.currency', string='Currency',track_visibility='onchange')
    rate = fields.Float(string="Tipo de Cambio ",track_visibility='onchange')

    out_payment_date = fields.Date(string='Fecha de Envío', default=fields.Date.context_today,track_visibility='onchange')
    in_payment_date = fields.Date(string='Fecha de Recibo',track_visibility='onchange')
    communication = fields.Char(string='Memo')
    payment_concept = fields.Char(string='Concepto de Pago')

    move_transient_id  = fields.Many2one('account.move',"Asiento Origen",track_visibility='onchange')
    move_transient_line_id =  fields.Many2one('account.move.line',compute='_compute_move_transient_line_id', string='Lineas')
    
    move_id   = fields.Many2one('account.move',"Asiento Destino")
    move_line_id =  fields.Many2one('account.move.line',compute='_compute_move_line_id', string='Lineas')

    partner_type = fields.Selection([('customer', 'Cliente'), ('supplier', 'Proveedor')], default='supplier')

    transaction_class_id = fields.Many2one('transaction.classification', string='Clasificación')

    state = fields.Selection(selection=[("draft", "Borrador"), ("confirmed", "Confirmado"), ("done", "Terminado"), ("cancel", "Cancel")], default="draft")
    
    report = fields.Binary('Prepared file', filters='.xls', readonly=True)

    def _compute_move_transient_line_id(self):
        line = self.env['account.move.line']
        lines = self.env['account.move.line'].search([
            ('move_id','=', self.move_transient_id.id)
        ])
        if len(lines) > 0 :
            line = lines
        return line

    def _compute_move_line_id(self):
        line = self.env['account.move.line']
        line = self.env['account.move.line'].search([
            ('move_id','=', self.move_id.id)
        ])
        return line

    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                company_id = vals.get('company_id', self.env.company.id)

                vals['name'] = self.env['ir.sequence'].with_company(company_id).next_by_code('intercompany.transfer') or '/'

        return super().create(vals_list)


    def validate(self):
        move_vals = {
            'date': self.out_payment_date,
            'journal_id': self.out_journal_id.id,
            'currency_id': self.currency_id.id if  self.currency_id.id else  self.out_company_id.currency_id.id ,
            'partner_id': self.out_company_id.partner_id.id,
            'ref': self.payment_concept,
            'tax_today': self.rate,
            'line_ids': [
                (0, 0, {
                    'name': self.payment_concept,
                    'amount_currency': self.amount * -1 if self.currency_id.id else 0 ,
                    'currency_id': self.currency_id.id  if self.currency_id.id  else 0 ,
                    'debit':  0,
                    'credit': self.amount * self.rate  if  self.currency_id.id else self.amount,
                    'partner_id': self.out_company_id.partner_id.id,
                    'account_id': self.out_journal_id.default_account_id.id,
                }),
                (0, 0, {
                    'name': self.payment_concept,
                    'amount_currency': self.amount * 1   if self.currency_id.id  else 0 ,
                    'currency_id': self.currency_id.id  if  self.currency_id.id  else 0 ,
                    'debit': self.amount * self.rate  if  self.currency_id.id else self.amount,
                    'credit': 0 ,
                    'partner_id': self.out_company_id.partner_id.id,
                    'account_id': self.out_destination_account_id.id,
                }),
                
            ],
        }
        self.move_transient_id = self.env['account.move'].create(move_vals)
        self.state = "confirmed"
    
    def terminar(self):
        move_vals_v2 = {
            'date': self.in_payment_date,
            'journal_id': self.in_journal_id.id,
            'currency_id': self.currency_id.id if  self.currency_id.id else  self.in_company_id.currency_id.id ,
            'partner_id': self.in_company_id.partner_id.id,
            'ref': self.payment_concept,
            'tax_today': self.rate,
            'line_ids': [
                (0, 0, {
                    'name': self.payment_concept,
                    'amount_currency': self.amount * -1   if self.currency_id.id   else 0 ,
                    'currency_id': self.currency_id.id    if  self.currency_id.id  else 0 ,
                    'credit': self.amount * self.rate if self.currency_id.id else self.amount,
                    'partner_id': self.in_company_id.partner_id.id,
                    'account_id': self.in_destination_account_id.id,
                }),
                (0, 0, {
                    'name': self.payment_concept,
                    'amount_currency': self.amount * 1  if self.currency_id.id  else 0 ,
                    'currency_id': self.currency_id.id  if self.currency_id.id  else 0 ,
                    'debit': self.amount * self.rate  if  self.currency_id.id else self.amount ,
                    'partner_id': self.in_company_id.partner_id.id,
                    'account_id': self.in_journal_id.default_account_id.id,
                }),
                
                
            ],
        }
        self.move_id = self.env['account.move'].create(move_vals_v2)
        self.move_transient_id.action_post()
        self.move_id.action_post()
        self.state = "done"

    def draft(self):
        self.state = "draft"
             
    def cancel(self):
        if self.move_id.id:
            if self.move_id == 'draft':
                self.move_id.unlink()
            else:
                self.move_id.button_draft()
                self.move_id.name = '/'
                self.move_id.restrict_mode_hash_table = False
                self.move_id.unlink()
        if self.move_transient_id.id:
            self.move_transient_id.button_draft()
            self.move_transient_id.name = '/'
            self.move_transient_id.restrict_mode_hash_table = False
            self.move_transient_id.unlink()
        self.state = 'cancel'

class TransactionClassification(models.Model):
    _name = 'transaction.classification'
    _description = 'Clasificación de transacciones en tesorería'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Nombre')
    type_transaction = fields.Selection([('nacional', 'Nacional'), ('extranjera', 'Extranjera')],string='Tipo', tracking=True)