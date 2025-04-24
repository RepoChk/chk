# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    team_id = fields.Many2one(
        'crm.team', 
        string='Equipo de Ventas',  # Nombre del campo en la interfaz
        related='invoice_user_id.partner_id.team_id',  # Relación encadenada para obtener el equipo
        store=True,  # Almacena el valor en la base de datos
        help="Equipo de ventas asociado al vendedor."  # Descripción del campo
    )

    is_confirmed_payment = fields.Boolean(
        string='¿Pago procesado?',
        help="Si este campo está marcado, indica que ya fue utilizado por el equipo de créditos y cobranzas",
        default=False,
        tracking=True,
    ) 
    
    validation_date = fields.Datetime(string='Fecha de Validación', store=True)

    currency_id_company = fields.Many2one("res.currency",
                                          string="Divisa compañia",
                                          default=lambda self: self.env.company.currency_id)
    account_holder_name = fields.Char(string='Nombre y Apellido del Titular de la Cuenta', store=True)
    account_holder_id_number = fields.Char(string='Documento de Identidad del Titular de la Cuenta', store=True)
    store_payment_date = fields.Date(string='Fecha del Pago', compute='_compute_payment_date', store=True)
    hr_payment_order_id = fields.Many2one(
        'hr.payment.order',
        string='Orden de Pago',
        readonly=True, 
    )
    from_payment_order = fields.Boolean(
        string='Desde orden de pago (HR)',
        readonly=True, 
        default=False,
    )
    is_concilied = fields.Boolean(
        string='¿Esta Conciliado?',
        help="Si este campo está marcado, se permite publicar los pagos que se reciben de los cliententes",
        default=False,
        tracking=True,
    )
    is_concilied_inv = fields.Boolean(compute='_compute_concilied')
    amount_due_invoices = fields.Monetary(string='Saldo adeudado (Facturas)', currency_field='currency_id_dif', compute='_compute_amount_due_invoices', store=False)
    residual_amount = fields.Monetary(string='Importe Residual (Pago)', currency_field='currency_id_dif', compute='_compute_residual_amount', store=False)
    amount_diferential = fields.Monetary(
        string='Ganancias/Pérdidas por Diferencia de Cambio',
        help=' Este campo se utiliza para registrar el impacto financiero que tiene la variación del tipo de cambio en transacciones en moneda extranjera.'
    )

    gc_payment_method_available = fields.Many2many(
        'gc.account.payment.method',
        compute='_compute_gc_payment_method_available',
    )

    gc_payment_method_id = fields.Many2one(
        'gc.account.payment.method',
        string='Modo de Pago',
        domain="[('id','in',gc_payment_method_available), ]",
    )

    requires_conciliation = fields.Boolean(
        related='gc_payment_method_id.requires_conciliation',
    )

    payment_free = fields.Boolean(
        string='Pago Libre',
        default=False,
        copy=False
    )

    payment_notes = fields.Text(
        string='payment_notes',
        tracking = True,
        copy = False
    )

    @api.depends('journal_id.gc_payment_method', 'payment_type')
    def _compute_gc_payment_method_available(self):
        for record in self:
            if record.payment_type == 'inbound':
                record.gc_payment_method_available = record.journal_id.gc_payment_method.filtered(lambda m: m.payment_type == 'inbound')
            elif record.payment_type == 'outbound':
                record.gc_payment_method_available = record.journal_id.gc_payment_method.filtered(lambda m: m.payment_type == 'outbound')
            else:
                record.gc_payment_method_available = False

    @api.depends('invoice_ids', 'amount_ref')
    def _compute_amount_due_invoices(self):
        for payment in self:
            total_due = sum(payment.invoice_ids.mapped('amount_residual_usd'))
            payment.amount_due_invoices = max(total_due - payment.amount_ref, 0)

    @api.depends('move_id.line_ids')  # Dependemos de las líneas del asiento
    def _compute_residual_amount(self):
        for payment in self:
            if payment.move_id:  # Verificamos que el pago tenga un asiento asociado
                # Filtrar las líneas de movimiento donde credit_usd es mayor que cero
                move_lines = payment.move_id.line_ids.filtered(lambda line: line.credit > 0)
                # Sumar el amount_residual_usd de las líneas filtradas
                payment.residual_amount = sum(move_lines.mapped('amount_residual_usd')) if payment.state == 'posted' else 0
            else:
                payment.residual_amount = 0  # Si no hay asiento, el residual es 0
                
    @api.depends('is_concilied')
    def _compute_concilied(self):
        for record in self:
            record.is_concilied_inv = record.is_concilied

    @api.onchange('invoice_ids')
    def _onchange_invoice_ids(self):
        for rec in self:
            move_type = 'out_invoice' if rec.payment_type == 'inbound' else 'in_invoice'

            if rec.invoice_ids:
                invoices_selected = rec.invoice_ids.sorted(key=lambda r: r.date)
                invoices_existing = self.env['account.move'].search([
                    ('partner_id', '=', rec.partner_id.id),
                    ('move_type', '=', move_type),
                    ('state', '=', 'posted'),
                    ('payment_state', 'in', ['not_paid', 'partial']),
                    ('company_id', '=', rec.company_id.id),
                ]).sorted(key=lambda r: r.date)

                for inv in invoices_existing:
                    if inv.date < invoices_selected[-1].date and inv.id not in invoices_selected.ids:
                        rec.invoice_ids = [(3, invoices_selected[-1].id)]
                        return {
                            'warning': {
                                'title': '¡ADVERTENCIA!',
                                'message': 'El cliente o proveedor posee facturas más antiguas sin pagar. La factura más reciente ha sido eliminada de la lista.'
                            }
                        }

    def action_open_invoice_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Facturas'),
            'res_model': 'account.move',
            'target': 'new',
            'view_mode': 'tree',
            'views': [
                (self.env.ref('gchakao_custom.view_account_move_tree_custom').id, 'tree'),
            ],
            'domain': [('id', 'in', self.invoices.ids),('id', 'not in', self.invoice_ids.ids)],
            'context': {
                'create': False,
                'edit': False,
                'default_payment_type': self.payment_type,
                'default_partner_id': self.partner_id.id,
                'default_company_id': self.company_id.id,
                'default_payment_id': self.payment_id.id,
                'invoice_ids': self.invoice_ids.ids,
            }
        }
    
    def _compute_payment_date(self):
        for payment in self:
            payment.store_payment_date = payment.date

    def action_post(self):
        # Llamar al método padre para realizar la acción de publicación
        res = super(AccountPayment, self).action_post()
        
        # Establecer la fecha de validación
        self.validation_date = fields.Datetime.now()
        
        # Verificar condiciones específicas solo si no es una transferencia interna
        if not self.is_internal_transfer:
            if self.payment_type == 'inbound':
                if self._context.get('form_payment'):
                    if self.gc_payment_method_id.requires_conciliation and not self.is_concilied:
                        raise ValidationError("Disculpe!!! No puede confirmar el pago sin que el Departamento de Tesorería lo haya Conciliado.")
        
        return res

    @api.constrains('payment_type', 'invoice_user_id')
    def _check_invoice_user_id(self):
        for record in self:
            if record.payment_type == 'inbound' and not record.invoice_user_id and not record.is_internal_transfer:
                raise ValidationError("El campo 'Vendedor' es obligatorio cuando el tipo de pago es 'Recibir/Cobro'.")
    
    def _compute_destination_account_id(self):
        super(AccountPayment, self)._compute_destination_account_id()
        for rec in self:
            if rec.payment_free:
                rec.destination_account_id = False
            else:
                pass

    def _get_account_payment_notification_user_id(self):
        user = self.env['ir.config_parameter'].sudo().get_param('gchakao_custom.account_payment_notification_user_id')
        return user

    def send_notification_account_payment(self, payment_order):
        activity_type_id = self.env.ref('gchakao_custom.mail_activity_type_alert_payment_with_op').id
        user = self._get_account_payment_notification_user_id()
        self.activity_schedule(
            activity_type_id=activity_type_id,
            user_id=user,
            note="Tiene un pago pendiente {} desde orden de pago {}.".format(self.name, payment_order),
        )

    def create(self, vals):
        # Llamar a la validación antes de crear el registro
        self._check_unique_bank_reference(vals)
        return super(AccountPayment, self).create(vals)

    def write(self, vals):
        # Verificar si el campo 'ref' ha cambiado antes de llamar a la validación
        if 'ref' in vals:
            self._check_unique_bank_reference(vals)
        return super(AccountPayment, self).write(vals)

    def _check_unique_bank_reference(self, vals):
        for record in self:
            # Verificar si el diario es de tipo banco
            if record.journal_id.type == 'bank':
                ref = vals.get('ref', record.ref)  # Obtener el valor de ref
                if ref:  
                    # Eliminar puntos de la referencia
                    cleaned_ref = ref.replace('.', '')

                    # Realizar la consulta SQL para verificar si existe una referencia igual
                    existing_reference = self.env['account.payment'].search_count([
                        ('ref', '=', cleaned_ref),
                        ('journal_id', '=', record.journal_id.id),
                        ('id', '!=', record.id)  # Excluir el registro actual
                    ])
                    
                    # Verificar los últimos 8 caracteres
                    last_chars = cleaned_ref[-8:]
                    existing_last = self.env['account.payment'].search_count([
                        ('ref', '!=', cleaned_ref),
                        ('journal_id', '=', record.journal_id.id),
                        ('ref', 'ilike', '%' + last_chars)  # Coincidencia de los últimos 8 caracteres
                    ])
                    
                    if existing_reference > 0 or existing_last > 0:
                        # Obtener información del pago existente
                        existing_payment = self.env['account.payment'].search([
                            ('ref', '=', cleaned_ref),
                            ('journal_id', '=', record.journal_id.id),
                            ('id', '!=', record.id)
                        ], limit=1)

                        payment_name = existing_payment.name or "No especificado"
                        journal_name = existing_payment.journal_id.name or "No especificado"
                        creator_name = existing_payment.create_uid.name or "No especificado"
                        invoice_user_id_name = existing_payment.invoice_user_id.partner_id.name or "No especificado"
                        date = existing_payment.date or "No especificado"
                        
                        raise ValidationError(
                            f"¡Advertencia! La referencia bancaria '{ref}' ya existe en este diario.\n"
                            f"Nombre del Pago Existente: {payment_name}\n"
                            f"Fecha: {date}\n"
                            f"Diario: {journal_name}\n"
                            f"Creado por: {creator_name}\n"
                            f"Vendedor: {invoice_user_id_name}\n"
                            f"Verifique que su registro 1) De ser incorrecto porfavor corrija. 2) De ser correcto porfavor comunicarse con el área de Tesorería para la revisión del Pago suministrado" 
                        )

    ############## CODIGO DE LA LOCALIZACION AJUSTADO ##############
    def register_move_igtf_divisa_payment(self):
        '''Este método realiza el asiento contable de la comisión según el porcentaje que indica la compañia'''
        #self.env['ir.sequence'].with_context(ir_sequence_date=self.date_advance).next_by_code(sequence_code)
        diario = self.journal_igtf_id or self.journal_id

        vals = {
            'date': self.date,
            'journal_id': diario.id,
            'currency_id': self.currency_id.id,
            'state': 'draft',
            'tax_today':self.tax_today,
            'ref':self.ref,
            'move_type': 'entry',
            'line_ids': [
                (0, 0, {
                'account_id': diario.inbound_payment_method_line_ids.payment_account_id.id if self.payment_type == 'inbound' and diario.inbound_payment_method_line_ids.payment_account_id.id else diario.suspense_account_id.id,
                'company_id': self.company_id.id,
                'currency_id': self.currency_id.id,
                'date_maturity': False,
                'ref': "Comisión IGTF Divisa",
                'date': self.date,
                'partner_id': self.partner_id.id,
                'name': "Comisión IGTF Divisa",
                'journal_id': self.journal_id.id,
                'credit': float(self.mount_igtf * self.tax_today) if not self.payment_type == 'inbound' else float(0.0),
                'debit': float(self.mount_igtf * self.tax_today) if self.payment_type == 'inbound' else float(0.0),
                'amount_currency': -self.mount_igtf if not self.payment_type == 'inbound' else self.mount_igtf,
            }),
                (0, 0, {
                'account_id': self.company_id.account_debit_wh_igtf_id.id if self.payment_type == 'inbound' else self.company_id.account_credit_wh_igtf_id.id,
                'company_id': self.company_id.id,
                'currency_id': self.currency_id.id,
                'date_maturity': False,
                'ref': "Comisión IGTF Divisa",
                'date': self.date,
                'name': "Comisión IGTF Divisa",
                'journal_id': self.journal_id.id,
                'credit': float(self.mount_igtf * self.tax_today) if self.payment_type == 'inbound' else float(0.0),
                'debit': float(self.mount_igtf * self.tax_today) if not self.payment_type == 'inbound' else float(0.0),
                'amount_currency': -self.mount_igtf if self.payment_type == 'inbound' else self.mount_igtf,
            }),
            ],
        }
        move_id = self.env['account.move'].with_context(check_move_validity=False).create(vals)

        if move_id:
            res = {'move_id_igtf_divisa': move_id.id}
            self.write(res)
            move_id.action_post()
        return True
        
    def action_draft(self):
        ''' posted -> draft '''
        res = super().action_draft()
        self.move_id_dif.button_draft()
        if self.move_id_igtf_divisa:
            if self.move_id_igtf_divisa.state == 'posted':
                self.move_id_igtf_divisa.button_draft()
