# coding: utf-8
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import json
from datetime import datetime, timedelta
import re

class AccountMove(models.Model):
    _inherit = "account.move"

    delivery_date = fields.Datetime(
        string='Fecha de Entrega',
        copy=False,
        store=True,
    )

    amount_payment_igtf_bs = fields.Float(
        string='Total IGFT Bs.',
        compute='_compute_amount_payment_igtf',
        default=0.0,
    )

    amount_payment_igtf_usd = fields.Float(
        string='Total IGFT USD',
        compute='_compute_amount_payment_igtf',
        default=0.0,
    )

    #Campo Filler Total
    filler_total = fields.Float(
        string='Filler Total', 
        compute='_compute_calculate_filler_total',
        store=True
    )

    #Datos de Importaciones
    origin_port = fields.Char(
        string="Puerto Origen",
        tracking=True
    )

    destination_port = fields.Char(
        string="Puerto Destino",
        tracking=True
    )

    origin_country_id = fields.Many2one(
        'res.country',
        string='País Origen',
        tracking=True
    )

    destination_country_id = fields.Many2one(
        'res.country',
        string='País Destino',
        tracking=True
    )

    branch_id = fields.Many2one(
        'res.company', 
        string='Sucursal', 
        domain="[('parent_id', '=', company_id)]", 
        tracking=True,
    )
    
    invoice_number = fields.Char(
        string='Número de Factura',
    )

    effective_base = fields.Float(
        string='Base Efectiva', digits=(12, 4),
        help="Campo para calcular la comisión de la cobranza",
        readonly=True
    )
    
    effective_date = fields.Datetime(
        string='Fecha Cierre',
        help="Campo para calcular la comisión de la cobranza",
        readonly=True
    )

    effective_day = fields.Integer(
        string='Dias de cobranza',
        help="Campo para calcular la comisión de la cobranza",
        readonly=True
    )

    sub_partner_ids = fields.Many2many(
        'res.partner', compute='_compute_sub_partner_ids', string='Sub-Proveedor (M2M)'
    )

    @api.depends('partner_id')
    def _compute_sub_partner_ids(self):
        for move in self:
            move.sub_partner_ids = move.partner_id.sub_provider_ids.ids

    sub_provider_id = fields.Many2one(
        'res.partner', string='Sub-Proveedor', domain="[('id', 'in', sub_partner_ids)]"
    )

    early_payment_id = fields.Many2one(
        comodel_name='account.move', string='Nota Pronto Pago'
    )
    
    commission_type = fields.Selection(
        string='Tipo de Comisión', 
        selection=[('normal', 'Normal'), ('reducida', 'Reducida')], 
        default='normal', 
        track_visibility='onchange'
    )

    invoice_date = fields.Date(
        string='Fecha de la Factura',
        default=fields.Date.context_today,
        required=False
    )

    def _domain_payment_term_user(self):
        payment_term_user = self.env.user.payment_term_ids.ids or []
        return [('id', 'in', payment_term_user), ('company_id', '=', self.company_id.id)]

    invoice_payment_term_id = fields.Many2one(
        comodel_name='account.payment.term',
        string='Payment Terms',
        compute='_compute_invoice_payment_term_id', store=True, readonly=False, precompute=True,
        check_company=True,
        domain=_domain_payment_term_user,
    )

    reason_cancellation = fields.Char(
        string='Razón de la Anulación',
        tracking=True,
        copy=False
    )
    
    void_invoice = fields.Boolean(
        string='Factura Anulada',
        help="Campo para bloquear boton de draft y cancel por anulación de factura",
        copy=False
    )
     
    motive = fields.Selection(
        string='Motivo de la Nota',
        selection=[
            ('d', 'Devolución'), 
            ('dr', 'Devolución por refacturación'), 
            ('dreu', 'Devolución por reubicación'), 
            ('dgar', 'Devolución por garantía'), 
            ('de', 'Descuento'),
            ('dp', 'Descuento por pronto pago'),
            ('dg', 'Descuento por garantía'),
            ('dcp', 'Descuento por compensación'),
            ('dc', 'Descuento por compensación 4%'),
            ('dcc', 'Descuento por compensación 2%'),
            ('ap', 'Ajuste de precio'),
        ],
        track_visibility='onchange',
        tracking=True,
        copy=False
    )

    tax_no_fiscal = fields.Boolean(
        string="Aplicar Impuesto No Fiscal?",
        help="Activar para reemplazar los impuestos en las líneas de este movimiento con los impuestos no fiscales configurados en el producto."
    )

    date_delivered_on = fields.Boolean(
        string='Fecha de Entrega agregada',
        default=False,
        copy=False
    )
    
    invoice_date_due_aux = fields.Datetime(
        string='Fecha de Vencimiento auxiliar',
        copy=False
    )

    @api.depends('invoice_line_ids.fillert')
    def _compute_calculate_filler_total(self):
        for rec in self:
            if rec.motive in ['d','dr', 'dreu', 'dgar', False]:
                filler = sum(line.fillert for line in rec.invoice_line_ids)
                rec.filler_total = filler
            else:
                rec.filler_total = 0

    @api.depends('partner_id')
    def _compute_invoice_payment_term_id(self):
        for move in self:
            payment_term_user_ids = self.env.user.payment_term_ids.ids
            if move.is_sale_document(include_receipts=True) and move.partner_id.property_payment_term_id in payment_term_user_ids:
                move.invoice_payment_term_id = move.partner_id.property_payment_term_id
            elif move.is_purchase_document(include_receipts=True) and move.partner_id.property_supplier_payment_term_id in payment_term_user_ids:
                move.invoice_payment_term_id = move.partner_id.property_supplier_payment_term_id
            else:
                move.invoice_payment_term_id = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['invoice_date'] = fields.Date.context_today(self)
        return super(AccountMove, self).create(vals_list)

    def write(self, vals):
        """Controla los permisos al intentar modificar la fecha."""
        if 'invoice_date' in vals:
            # Validar si el usuario tiene permisos
            if not self.env.user.has_group('gchakao_custom.group_edit_invoice_date'):
                raise UserError(_("No tienes permisos para modificar la fecha de la factura."))
        return super(AccountMove, self).write(vals)

    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        """Modifica dinámicamente la vista para que el campo sea solo lectura."""
        res = super(AccountMove, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if view_type == 'form' and not self.env.user.has_group('gchakao_custom.group_edit_invoice_date'):
            doc = etree.XML(res['arch'])
            for field in doc.xpath("//field[@name='invoice_date']"):
                field.set("readonly", "1")
            res['arch'] = etree.tostring(doc, encoding='unicode')
        return res

    @api.onchange('tax_no_fiscal')
    def _onchange_tax_no_fiscal(self):
        # Validar que el estado del documento sea 'draft'
        if self.state != 'draft':
            raise UserError("El documento debe estar en estado 'Borrador' para hacer cambios en este botón.")
        
        if self.tax_no_fiscal:
            for line in self.line_ids:  # Cambiar 'order_line' por 'line_ids' para account.move
                if line.product_id and line.product_id.customer_no_fiscal_taxes_ids:
                    # Asignar el primer impuesto no fiscal
                    line.tax_ids = line.product_id.customer_no_fiscal_taxes_ids[:1]
                else:
                    # Si no hay impuesto no fiscal, asignar el impuesto fiscal habitual
                    line.tax_ids = line.product_id.taxes_id
        else:
            for line in self.line_ids:
                if line.product_id and line.product_id.taxes_id:
                    # Al desactivar, asignar el primer impuesto fiscal
                    line.tax_ids = line.product_id.taxes_id[:1]  # Usa el primer impuesto configurado

    @api.depends('invoice_number','supplier_invoice_number','name')
    def _compute_display_name(self):
        for rec in self:
            invoice_number = rec.name
            if rec.move_type == 'out_invoice':
                invoice_number = rec.invoice_number or rec.name
            if rec.move_type == 'in_invoice':
                invoice_number = rec.supplier_invoice_number or rec.name
            rec.display_name = f"{invoice_number}"

    @api.depends('invoice_payments_widget')
    def _compute_amount_payment_igtf(self):
        for rec in self:
            payments = rec.sudo().invoice_payments_widget and rec.sudo().invoice_payments_widget['content'] or []
            amount_usd = 0
            amount_bs = 0
            if payments:
                unique_payments = {p['account_payment_id']: p for p in payments}.values()
                for p in unique_payments:
                    igtf = self.env['account.payment'].search([
                        ('id', '=', int(p['account_payment_id'])),
                        ('move_id_igtf_divisa', '!=', False)
                    ])
                    if igtf:
                        if igtf.currency_id.id == igtf.currency_id_company.id:
                            amount_bs += igtf.mount_igtf
                            amount_usd += igtf.mount_igtf / igtf.move_id_igtf_divisa.tax_today
                        else:
                            amount_bs += igtf.mount_igtf * igtf.move_id_igtf_divisa.tax_today
                            amount_usd += igtf.mount_igtf
            rec.amount_payment_igtf_bs = amount_bs
            rec.amount_payment_igtf_usd = amount_usd

    def action_post(self):
        # Itera sobre cada movimiento en caso de que se manejen múltiples registros
        for move in self:
            # Verifica si el tipo de movimiento es una factura de salida
            if move.move_type in ('out_invoice', 'out_refund', 'out_receipt'):
                # Verifica si se ha seleccionado un diario
                if not move.journal_id:
                    raise UserError('Debe seleccionar un diario')

                # Asigna las secuencias si no están ya asignadas
                if not move.invoice_number:
                    num = self._check_unique_invoice_number()
                    if num:
                        raise ValidationError(f'Ya existe una factura con el número [{num.invoice_number}]\n para el contacto {num.partner_id.name}\n en el diario {num.journal_id.name}.')
                    move.invoice_number = move.journal_id.invoice_seq_id.next_by_id()
                if not move.nro_ctrl:
                    ctrl = self._check_unique_nro_ctrl()
                    if ctrl:
                        raise ValidationError(f'Ya existe una factura con el número de control [{ctrl.nro_ctrl}]\n para el contacto {ctrl.partner_id.name}\n en el diario {ctrl.journal_id.name}.')
                    move.nro_ctrl = move.journal_id.invoice_ctrl_seq_id.next_by_id()
                
                # Habilita o deshabilita el campo sin_cred basado en la configuración del diario
                move.sin_cred = move.journal_id.exclude_fiscal_documents
                
                # Asegúrate de que el cambio se guarde
                move.write({'sin_cred': move.sin_cred})
        # Llama al método original para publicar la factura
        return super(AccountMove, self).action_post()

    def action_assign_invoices(self):
        selected_invoice_ids = self.env.context.get('active_ids', [])
        if selected_invoice_ids:
            payment = self.env['account.payment'].browse(self.env.context.get('default_payment_id'))
            moves = self.env.context.get('invoice_ids')
            if payment:
                selected_invoices = self.env['account.move'].browse(selected_invoice_ids)
                # Obtenemos el cliente de las facturas seleccionadas
                partner_id = selected_invoices[0].partner_id.id if selected_invoices else None
                
                if partner_id:
                    # Buscar facturas más antiguas y sin pagar del mismo cliente
                    older_unpaid_invoices = self.env['account.move'].search([
                        ('partner_id', '=', partner_id),
                        ('state', '=', 'posted'),
                        ('payment_state', 'in', ['not_paid', 'partial']),
                        ('invoice_date', '<', min(selected_invoices.mapped('invoice_date'))),
                        ('id', 'not in', moves),
                        ('company_id', '=', self.company_id.id),
                    ])
                    
                    if older_unpaid_invoices:
                        raise UserError('Existen facturas más antiguas y sin pagar. Por favor, seleccione las facturas más antiguas antes de proceder.')
                    
                    payment.invoice_ids = [(4, invoice_id) for invoice_id in selected_invoice_ids]

    #CALCULO DE COMISIONES
    @api.depends('invoice_payment_state')
    def _constrains_invoice_payments_widget(self):
        for item in self:
            if item.invoice_payment_state == "paid":
                item.cal_comission()
            else :
                item.effective_base = 0
                item.effective_date = item.date

    def cal_comission(self):
        for rec in self:
            rec.effective_base = rec.amount_untaxed
            if rec.invoice_payments_widget :
                parse_dict = json.loads(rec.invoice_payments_widget)
                if parse_dict:
                    rec.effective_date = parse_dict['content'][0]['date']
                    for pay in parse_dict.get('content'):
                        move_id = self.env['account.move'].search([('id', '=', pay['move_id'])])
                        d = datetime.strptime(pay['date'],'%Y-%m-%d').date()
                        if rec.effective_date  < d :
                            rec.effective_date = pay['date']
                        if move_id.type == "out_refund":
                            rec.effective_base -= move_id.amount_untaxed
                if rec.effective_date and rec.invoice_date:
                    delta = rec.effective_date - rec.invoice_date
                    rec.effective_day = int(delta.days)
                    rec.effective_day = int(delta.days)

    def _check_unique_invoice_number(self):
        sequence = self.journal_id.invoice_seq_id

        if not sequence:
            raise UserError(f'El diario [{sequence.name}] no tiene configurado la secuencia')

        # Obtener el prefijo, relleno y el siguiente número de la secuencia
        prefix = sequence.prefix or ''
        padding = sequence.padding or 0
        number_next_actual = sequence.number_next_actual or 0

        # Formatear el siguiente número con el prefijo y el relleno adecuado
        number_next = f'{prefix}{str(number_next_actual).zfill(padding)}'

        # Verificar si ya existe una factura con este número
        existing = self.env['account.move'].search([
            ('invoice_number', '=', number_next),
            ('journal_id', '=', self.journal_id.id),
            ('company_id', '=', self.company_id.id),
            ('id', '!=', self.id)
        ], limit=1)

        return existing

    def _check_unique_nro_ctrl(self):
        sequence = self.journal_id.sequence_nro_ctrl_id
        if not sequence:
            raise UserError(f'El diario [{sequence.name}] no tiene secuencias configuradas')

        prefix = sequence.prefix or ''
        padding = sequence.padding or 0
        number_next_actual = sequence.number_next_actual or 0

        # Formatear el siguiente número con el prefijo y el relleno adecuado
        number_next = f'{prefix}{str(number_next_actual).zfill(padding)}'
        existing = self.env['account.move'].search([
            ('nro_ctrl', '=', number_next),
            ('journal_id', '=', self.journal_id.id),
            ('company_id', '=', self.company_id.id),
            ('id', '!=', self.id)
        ], limit=1)
        return existing

    def get_early_payment(self):
        for item in self:
            if len(item.early_payment_id) < 1:
                invoice = {
                    'move_type': 'out_refund',
                    'partner_id': item.partner_id.id,
                    'invoice_user_id': item.invoice_user_id.id,
                    'team_id': item.team_id.id,
                    'rif': item.rif,
                    'partner_shipping_id': item.partner_shipping_id.id,
                    'filler_total': 0,
                    'invoice_date': fields.Date.today(),
                    'invoice_payment_term_id': item.invoice_payment_term_id.id,
                    'invoice_date_due': item.invoice_date_due,
                    'journal_id': item.journal_id.id,
                    'branch_id': item.branch_id.id,
                    'tax_today': item.tax_today,
                    'currency_id_dif': item.currency_id_dif.id,
                    'company_id': item.company_id.id,
                    'currency_id': item.currency_id.id,
                    'ref': item.invoice_number,
                    'reversed_entry_id_new':item.id,
                    'invoice_line_ids': [],
                }
                invoice_line_ids = []
                for line in item.invoice_line_ids:
                    precio_nuevo = ((line.price_subtotal / line.quantity) * line.early_payment_discount) / 100
                    data = {
                        'product_id': line.product_id.id,
                        'account_id': line.account_id.id,
                        'quantity': line.quantity,
                        'price_unit': precio_nuevo,
                        'early_payment_discount': line.early_payment_discount,
                        'tax_ids': line.tax_ids.ids,
                        'sale_line_ids': line.sale_line_ids.ids,
                    }
                    invoice_line_ids.append(data)

                for line in invoice_line_ids:
                    invoice['invoice_line_ids'].append((0, 0, line))

                factura = item.env['account.move'].create(invoice)
                
                item.early_payment_id = factura.id

                action = item.env.ref('account.action_move_out_invoice_type').read()[0]
                form_view = [(item.env.ref('account.view_move_form').id, 'form')]
                action['views'] = form_view
                action['res_id'] = factura.id

                return action
            else:
                raise ValidationError('Esta factura ya posee una nota por pronto pago')

    def action_void_invoice_wizard(self):
        self.ensure_one()
        return {
            'name': 'Seleccionar la factura',
            'type': 'ir.actions.act_window',
            'res_model': 'void.invoice',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_move_id': self.id,
            },
        }

    def suma_alicuota_iguales_iva(self):
        # raise UserError(_('xxx = %s')%self.wh_iva_id)
        for rec in self:
            if rec.move_type == 'in_invoice' or rec.move_type == 'in_refund' or rec.move_type == 'in_receipt':
                type_tax_use = 'purchase'
                porcentaje_ret = rec.company_id.partner_id.wh_iva_rate
            if rec.move_type == 'out_invoice' or rec.move_type == 'out_refund' or rec.move_type == 'out_receipt':
                type_tax_use = 'sale'
                porcentaje_ret = rec.partner_id.wh_iva_rate
            if rec.move_type == 'in_invoice' or rec.move_type == 'out_invoice':
                tipo_doc = "01"
            if rec.move_type == 'in_refund' or rec.move_type == 'out_refund':
                tipo_doc = "03"
            if rec.move_type == 'in_receipt' or rec.move_type == 'out_receipt':
                tipo_doc = "02"

            if rec.move_type in ('in_invoice', 'in_refund', 'in_receipt', 'out_receipt', 'out_refund', 'out_invoice'):
                # ****** AQUI VERIFICA SI LAS LINEAS DE FACTURA TIENEN ALICUOTAS *****
                verf = rec.invoice_line_ids.filtered(
                lambda line: line.display_type not in ('line_section', 'line_note'))
                # raise UserError(_('verf= %s')%verf)
                for det_verf in verf:
                    # raise UserError(_('det_verf.tax_ids.id= %s')%det_verf.tax_ids.id)
                    if not det_verf.tax_ids and not rec.sin_cred:
                        raise UserError(_('Las Lineas de la Factura deben tener un tipo de alicuota o impuestos'))
                # ***** FIN VERIFICACION
                lista_impuesto = rec.invoice_line_ids.mapped('tax_ids')
                # ('aliquot','not in',('general','exempt')
                base = 0
                total = 0
                total_impuesto = 0
                total_exento = 0
                alicuota_adicional = 0
                alicuota_reducida = 0
                alicuota_general = 0
                base_general = 0
                base_reducida = 0
                base_adicional = 0
                retenido_general = 0
                retenido_reducida = 0
                retenido_adicional = 0
                valor_iva = 0

                for det_tax in lista_impuesto:
                    tipo_alicuota = det_tax.appl_type

                    # raise UserError(_('tipo_alicuota: %s')%tipo_alicuota)
                    if det_tax.type_tax == 'iva':
                        det_lin = rec.invoice_line_ids.filtered(lambda line: det_tax in line.tax_ids)
                        if det_lin:
                            for det_fac in det_lin:  # USAR AQUI ACOMULADORES
                                if rec.state != "cancel":
                                    
                                    base = base + det_fac.price_subtotal
                                    total = total + det_fac.price_total
                                    total_impuesto = total_impuesto + (det_fac.price_total - det_fac.price_subtotal)
                                    if tipo_alicuota == "general":
                                        alicuota_general = alicuota_general + (det_fac.price_total - det_fac.price_subtotal)
                                        base_general = base_general + det_fac.price_subtotal
                                        valor_iva = det_tax.amount
                                    if tipo_alicuota == "exento":
                                        total_exento = total_exento + det_fac.price_subtotal
                                    if tipo_alicuota == "reducido":
                                        alicuota_reducida = alicuota_reducida + (det_fac.price_total - det_fac.price_subtotal)
                                        base_reducida = base_reducida + det_fac.price_subtotal
                                    if tipo_alicuota == "adicional":
                                        alicuota_adicional = alicuota_adicional + (det_fac.price_total - det_fac.price_subtotal)
                                        base_adicional = base_adicional + det_fac.price_subtotal
                                
                            total_ret_iva = (total_impuesto * porcentaje_ret) / 100
                            retenido_general = (alicuota_general * porcentaje_ret) / 100
                            retenido_reducida = (alicuota_reducida * porcentaje_ret) / 100
                            retenido_adicional = (alicuota_adicional * porcentaje_ret) / 100

                            if rec.move_type in ('in_refund','out_refund'):
                                base *= -1 
                                total *= -1 
                                total_impuesto *= -1 
                                alicuota_general *= -1 
                                valor_iva *= -1 
                                total_exento *= -1 
                                alicuota_reducida *= -1 
                                alicuota_adicional *= -1 
                                total_ret_iva *= -1 
                                base_adicional *= -1 
                                base_reducida *= -1 
                                base_general *= -1 
                                retenido_general *= -1 
                                retenido_reducida *= -1 
                                retenido_adicional *= -1 
                            # raise UserError(f'price_subtotal {det_fac.price_subtotal} \n \
                            #         price_total {det_fac.price_total} \n \
                            #         total_base {base} \n \
                            #         total_con_iva {total} \n \
                            #         total_valor_iva {total_impuesto} \n \
                            #         total_exento {total_exento} \n \
                            #         alicuota_reducida {alicuota_reducida} \n \
                            #         alicuota_adicional {alicuota_adicional} \n \
                            #         alicuota_general {alicuota_general} \n \
                            #         base_adicional {base_adicional} \n \
                            #         det_lin {det_lin} \n \
                            #         ')
                            values = {
                                'total_con_iva': total,  # listo
                                'total_base': base,  # listo
                                'total_valor_iva': total_impuesto,  # listo
                                'tax_id': det_tax.id,
                                'invoice_id': rec.id,
                                'vat_ret_id': rec.wh_iva_id.id,
                                'nro_comprobante': rec.wh_iva_id.name,
                                'porcentaje_ret': porcentaje_ret,
                                'total_ret_iva': total_ret_iva,
                                'type': rec.move_type,
                                'state': rec.state,
                                'state_voucher_iva': rec.wh_iva_id.state,
                                'tipo_doc': tipo_doc,
                                'total_exento': total_exento,  # listo
                                'alicuota_reducida': alicuota_reducida,  # listo
                                'alicuota_adicional': alicuota_adicional,  # listo
                                'alicuota_general': alicuota_general,  # listo
                                'fecha_fact': rec.date,
                                'fecha_comprobante': rec.wh_iva_id.date,
                                'base_adicional': base_adicional,  # listo
                                'base_reducida': base_reducida,  # listo
                                'base_general': base_general,  # listo
                                'retenido_general': retenido_general,
                                'retenido_reducida': retenido_reducida,
                                'retenido_adicional': retenido_adicional,
                            }
                            self.env['account.move.line.resumen'].create(values)

                # raise UserError(_('valor_iva= %s')%valor_iva)

    @api.depends('invoice_payments_widget','line_ids.matched_debit_ids', 'line_ids.matched_credit_ids')
    def _compute_igtf_aplicado(self):
        #buscar en todos los pagos aplicados cual tiene igtf
        for rec in self:
            widget = rec.invoice_payments_widget if rec.invoice_payments_widget else {}
            content = widget.get('content', [])
            igtf_base = 0
            igtf_aplicado = 0
            igtf_maximo = (abs(rec.amount_total_usd) * 0.03)
            igtf_base_maximo = abs(rec.amount_total_usd)
            if content:
                for c in content:
                    account_payment_id = c.get('account_payment_id')
                    payment = self.env['account.payment'].search([('id', '=', account_payment_id),('aplicar_igtf_divisa', '=', True)])
                    if payment:
                        igtf_aplicado += payment.mount_igtf
                        igtf_base += payment.amount
            if igtf_aplicado > igtf_maximo:
                igtf_aplicado = igtf_maximo
            if igtf_base > igtf_base_maximo:
                igtf_base = igtf_base_maximo
            rec.igtf_aplicado = igtf_aplicado
            rec.igtf_base = igtf_base

    def get_invoice_number_digits(self):
        return re.sub(r'\D', '', self.invoice_number)

    @api.constrains('supplier_invoice_number')
    def _constrains_supplier_invoice_number(self):
        for rec in self:
            supplier_invoice_number = rec.supplier_invoice_number if rec.supplier_invoice_number not in ['N/P','NA'] else ''
            if supplier_invoice_number:
                existing = self.env['account.move'].search([
                    ('supplier_invoice_number', '=', supplier_invoice_number),
                    ('partner_id', '=', rec.partner_id.id),
                    ('id', '!=', rec.id)
                ], limit=1)
                if existing:
                    raise ValidationError(f'El número de factura [{supplier_invoice_number}] ya existe para el proveedor {rec.partner_id.name}')

    @api.onchange('partner_id')
    def _onchange_gc_partner_id(self):
        for rec in self:
            rec.supplier_invoice_number = '' if rec.supplier_invoice_number not in ['N/P','NA'] else rec.supplier_invoice_number

    @api.depends('needed_terms')
    def _compute_invoice_date_due(self):
        super()._compute_invoice_date_due()
        for rec in self:
            if rec.date_delivered_on:
                rec.invoice_date_due = rec.invoice_date_due_aux

    def actualizar_vencimiento(self, invoices):
        for inv in invoices:
            if inv.delivery_date and inv.invoice_date_due:  
                
                fecha_factura = inv.invoice_date
                fecha_entrega = inv.delivery_date.date()
                dias_diferencia = (fecha_entrega - fecha_factura).days
                fecha_vencimiento_real = inv.invoice_date_due + timedelta(days=dias_diferencia)

                fecha_vencimiento_calculada = inv.invoice_date + timedelta(days=inv.invoice_payment_term_id.line_ids.nb_days)
                fecha_vencimiento_calculada_entrega = fecha_vencimiento_calculada + timedelta(days=dias_diferencia)

                #raise UserError(f'factura: {inv.invoice_number}\n Fecha de factura {inv.invoice_date}\n Fecha de vencimiento: {inv.invoice_date_due}\n Fecha de vencimiento calculada: {fecha_vencimiento_calculada}\n Fecha de vencimiento calculada entrega: {fecha_vencimiento_calculada_entrega}')

                if fecha_vencimiento_calculada == fecha_vencimiento_real:
                    inv.invoice_date_due_aux = fecha_vencimiento_calculada
                    inv.date_delivered_on = True
                else:
                    inv.invoice_date_due_aux = fecha_vencimiento_calculada_entrega
                    inv.invoice_date_due = fecha_vencimiento_calculada_entrega
                    inv.date_delivered_on = True
                    for line in inv.line_ids: 
                        if line.date_maturity:
                            line.date_maturity = inv.invoice_date_due