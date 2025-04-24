# coding: utf-8
from odoo import models, fields, api, _, SUPERUSER_ID
from datetime import datetime
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta 
import json

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    fillert = fields.Float(
        string='Filler Total', 
        copy=False, 
        compute='_compute_calculate_fillert', 
        store=True
    )

    exhibitor_request = fields.Boolean(
        string='¿Solicitar Exhibidores?', 
        tracking=True
    )

    logistic_active = fields.Boolean(
        string='¿Requiere despacho?', 
        tracking=True
    )
    
    logistic_use = fields.Boolean(
        string='¿Despacho en proceso?', 
        tracking=True
    )

    truck_payment = fields.Boolean(
        string='¿Pago contra camión?', 
        tracking=True
    )
    
    approvals_ids = fields.One2many(
        'approval.request', 
        'order_id', 
        string='Aprobaciones Enviadas'
    )

    approver_ids = fields.Many2many(
        'res.users', 
        string='Aprobadores', 
        readonly=True, 
        compute='_compute_approver',
        store=True
    )

    remove_approval = fields.Boolean(compute='_compute_remove_approval',)

    approvals_approver_ids = fields.Many2many('approval.approver', string='Aprobaciones', compute='_compute_approvals_approver_ids')

    due_date = fields.Date(string="Fecha de Vencimiento", compute="_compute_due_date", store=True)

    @api.depends('create_date', 'payment_term_id')
    def _compute_due_date(self):
        for order in self:
            if order.create_date and order.payment_term_id and order.payment_term_id.line_ids:
                nb_days = order.payment_term_id.line_ids[0].nb_days
                if nb_days is not None:
                    order.due_date = order.create_date + timedelta(days=nb_days)
                else:
                    order.due_date = None
            else:
                order.due_date = None

    @api.depends('approvals_ids')
    def _compute_approvals_approver_ids(self):
        for rec in self:
            rec.approvals_approver_ids = []
            if len(rec.approvals_ids) >= 1:
                rec.approvals_approver_ids = rec.approvals_ids.mapped('approver_ids')

    # user_id = fields.Many2one(
    #     comodel_name='res.users',
    #     string="Salesperson",
    #     compute='_compute_user_id',
    #     store=True, readonly=False, precompute=True, index=True,
    #     tracking=2,
    #     domain=lambda self: "[('groups_id', '=', {}), ('share', '=', False), ('company_ids', '=', company_id)]".format(
    #         self.env.ref("sales_team.group_sale_salesman").id
    #     ))

    # @api.depends('partner_id')
    # def _compute_user_id(self):
    #     for order in self:
    #         if order.partner_id:
    #             # Verificar si el usuario logueado pertenece a un equipo de ventas crm.team
    #             if self.env['crm.team'].search_count([('user_id', '=', self.env.uid)]) > 0:
    #                 order.user_id = self.env.user
    #             # elif not (order._origin.id and order.user_id):
    #             #     # Recompute the salesman on partner change
    #             #     #   * if partner is set (is required anyway, so it will be set sooner or later)
    #             #     #   * if the order is not saved or has no salesman already
    #             #     order.user_id = (
    #             #         order.partner_id.user_id
    #             #         # or order.partner_id.commercial_partner_id.user_id
    #             #         # or (self.user_has_groups('sales_team.group_sale_salesman') and self.env.user)
    #             #     )

    @api.depends('partner_id')
    def _compute_user_id(self):
        for order in self:
            if order.partner_id:
                if self.env['crm.team'].search_count([('member_ids', 'in', [self.env.uid])]) > 0:
                    order.user_id = self.env.user
                else:
                    # Recompute the salesman on partner change
                    #   * if partner is set (is required anyway, so it will be set sooner or later)
                    #   * if the order is not saved or has no salesman already
                    order.user_id = (
                        order.partner_id.user_id
                        or order.partner_id.commercial_partner_id.user_id
                        or (self.user_has_groups('sales_team.group_sale_salesman') and self.env.user)
                    )


    @api.depends('create_uid','user_id')
    def _compute_remove_approval(self):
        self.remove_approval = self.env.user.remove_approval

    
    is_approval = fields.Boolean(
        string="Tiene aprobación", 
        compute="_compute_is_approval"
    )

    branch_id = fields.Many2one(
            'res.company', 
            string='Sucursal', 
            domain="[('parent_id', '=', company_id)]", 
            tracking=True
        )

    @api.constrains('branch_id')
    def _check_branch_id_required(self):
        """
        Verifica si el campo branch_id es obligatorio al crear y confirmar el pedido.
        - No es obligatorio al crear para el grupo "Fuerza de Ventas".
        - Es obligatorio al confirmar para el grupo "Fuerza de Ventas".
        - Es obligatorio tanto al crear como al confirmar para otros usuarios.
        """
        for record in self:
            # Verifica si el usuario pertenece al grupo "Fuerza de Ventas"
            if self.env.user.has_group('gchakao_custom.group_sales_force_user'):
                # Si el usuario pertenece al grupo, se verifica solo al confirmar
                if record.state == 'sale' and not record.branch_id:
                    raise ValidationError("El campo 'Sucursal' es obligatorio al confirmar el pedido.")
            else:
                # Si el usuario no pertenece al grupo, se verifica en ambos estados
                if not record.branch_id:
                    raise ValidationError("El campo 'Sucursal' es obligatorio tanto al crear como al confirmar el pedido.")
    
                
    # situation = fields.Selection(
    #     string='Situación',
    #     selection=[
    #         ('apartado', 'Apartado'),
    #         ('analisis', 'Análisis'),
    #         ('aprobado_por_facturar', 'Aprobado por facturar'),
    #         ('facturado_por_entregar', 'Facturado sin entregar'),
    #         ('facturado_y_entregado', 'Facturado y entregado'),
    #         ('en_proceso', 'En Proceso'),
    #         ('cancelado', 'Cancelado')
    #     ],
    #     compute='_compute_situation',
    #     store=True,
    #     readonly=True
    # )

    # @api.depends('state', 'picking_ids.state', 'approvals_ids.request_status', 'invoice_status')
    # def _compute_situation(self):
    #     for order in self:
    #         if order.state == 'cancel':
    #             order.situation = 'cancelado'
    #             continue

    #         pickings = order.picking_ids
    #         approvals = order.approvals_ids.sorted('create_date', reverse=True)  # Ordena por la aprobación más reciente
    #         invoice_status = order.invoice_status

    #         has_approved = any(approval.request_status == 'approved' for approval in approvals)  # Verifica si hay alguna aprobación aprobada

    #         if pickings.filtered(lambda p: p.state == 'assigned'):
    #             if not approvals:
    #                 order.situation = 'apartado'
    #             elif any(approval.request_status == 'pending' for approval in approvals) and invoice_status == 'to invoice':
    #                 order.situation = 'analisis'
    #             elif has_approved and invoice_status == 'to invoice':
    #                 order.situation = 'aprobado_por_facturar'
    #             elif has_approved and invoice_status == 'invoiced':
    #                 order.situation = 'facturado_por_entregar'
    #             else:
    #                 order.situation = 'en_proceso'
    #         elif pickings and all(p.state == 'done' for p in pickings) and invoice_status == 'invoiced':
    #             order.situation = 'facturado_y_entregado'
    #         else:
    #             order.situation = 'en_proceso'
    # 
    # @api.model
    # def cron_recalculate_situation(self):
    #     orders = self.search([])
    #     orders._compute_situation()
    
    situation = fields.Selection([
        ('por_iniciar', 'Por Iniciar'),
        ('en_proceso', 'En Proceso'),
        ('apartado', 'Apartado'),
        ('analisis', 'Análisis'),
        ('aprobado_por_facturar', 'Aprobado por facturar'),
        ('facturado_por_entregar', 'Facturado sin entregar'),
        ('facturado_y_entregado', 'Facturado y entregado'),
        ('factura_anulada', 'Factura Anulada'),
        ('servicio_en_proceso', 'Servicio en Proceso'),
        ('servicio_analisis', 'Servicio Análisis'),
        ('servicio_aprobado_por_facturar', 'Servicio Aprobado por Facturar'),
        ('servicio_facturado', 'Servicio Facturado'),
        ('cancelado', 'Cancelado')
    ], string='Situación', compute='_compute_situation', store=True, readonly=True)

    @api.depends('state', 'picking_ids.state', 'approvals_ids.request_status', 
                 'order_line.product_id.detailed_type', 'invoice_ids', 'order_line.qty_delivered',
                 'invoice_ids.state', 'picking_ids', 'approvals_ids')
    def _compute_situation(self):
        for order in self:
            if order.state == 'cancel':
                order.situation = 'cancelado'
                continue

            # Verificar si no tiene ninguna actividad
            has_no_activity = (
                not order.approvals_ids and
                not order.picking_ids and
                not order.invoice_ids
            )
            if has_no_activity:
                order.situation = 'por_iniciar'
                continue

            # Verificar si tiene factura anulada por NC total
            if order._has_total_credit_note():
                order.situation = 'factura_anulada'
                continue

            # Verificar si TODAS las facturas están canceladas
            all_invoices_canceled = all(
                i.state == 'cancel' 
                for i in order.invoice_ids
            ) if order.invoice_ids else False
            if all_invoices_canceled:
                order.situation = 'factura_anulada'
                continue

            # Obtener datos necesarios
            product_types = order.order_line.mapped('product_id.detailed_type')
            is_stock_only = all(pt == 'product' for pt in product_types)
            is_service_only = all(pt == 'service' for pt in product_types)
            is_mixed = not is_stock_only and not is_service_only

            # Obtener última aprobación
            last_approval = order.approvals_ids.sorted('create_date', reverse=True)[:1]
            approval_status = last_approval.request_status if last_approval else False

            # Cambiar a análisis si se envió la aprobación
            if approval_status == 'pending':
                order.situation = 'analisis'
                continue

            # Verificar si está facturado (independiente del invoice_status)
            is_invoiced = bool(order.invoice_ids.filtered(
                lambda i: i.state == 'posted' and i.move_type == 'out_invoice'
            ))

            # Verificar si tiene pickings en estado assigned
            has_picking_assigned = any(
                p.state == 'assigned' 
                for p in order.picking_ids
            )

            # Si tiene pickings assigned y no tiene aprobaciones, debe estar en apartado
            if has_picking_assigned and not approval_status and order.is_approval:
                order.situation = 'apartado'
                continue

            if is_service_only:
                order.situation = order._get_service_situation(
                    approval_status, 
                    is_invoiced
                )
            elif is_stock_only or is_mixed:
                order.situation = order._get_stock_situation(
                    approval_status, 
                    is_invoiced
                )
            else:
                order.situation = 'en_proceso'

    def _has_total_credit_note(self):
        """Verifica si el pedido tiene una nota de crédito por el valor total de la factura"""
        self.ensure_one()
        invoices = self.invoice_ids.filtered(lambda i: i.state == 'posted' and i.move_type == 'out_invoice')
        credit_notes = self.invoice_ids.filtered(lambda i: i.state == 'posted' and i.move_type == 'out_refund')
        
        for invoice in invoices:
            invoice_amount = abs(invoice.amount_total_usd)
            related_credit_notes = credit_notes.filtered(lambda cn: cn.reversed_entry_id == invoice)
            credit_note_amount = sum(cn.amount_total_usd for cn in related_credit_notes)
            
            if abs(credit_note_amount) >= invoice_amount:
                return True
        return False

    def _get_stock_situation(self, approval_status, is_invoiced):
        """Determina la situación para productos almacenables o mixtos"""
        self.ensure_one()

        # Verificar si está totalmente entregado
        is_fully_delivered = all(
            line.product_uom_qty <= line.qty_delivered 
            for line in self.order_line 
            if line.product_id.detailed_type == 'product'
        )

        # Verificar si tiene al menos un picking en estado 'assigned'
        has_picking_assigned = any(
            p.state == 'assigned' 
            for p in self.picking_ids
        )

        # FACTURADO Y ENTREGADO
        if (is_fully_delivered and 
            is_invoiced and
            (approval_status == 'approved' or not self.is_approval)):
            return 'facturado_y_entregado'

        # FACTURADO POR ENTREGAR
        if (is_invoiced and 
            not is_fully_delivered and
            (approval_status == 'approved' or not self.is_approval)):
            return 'facturado_por_entregar'

        # APROBADO POR FACTURAR
        if approval_status == 'approved' and not is_invoiced:
            return 'aprobado_por_facturar'

        # ANÁLISIS
        if approval_status == 'pending':
            return 'analisis'

        # APARTADO
        if has_picking_assigned:
            return 'apartado'

        # EN PROCESO (por defecto)
        return 'en_proceso'

    def _get_service_situation(self, approval_status, is_invoiced):
        """Determina la situación para servicios"""
        # SERVICIO FACTURADO
        if is_invoiced:
            return 'servicio_facturado'

        # SERVICIO APROBADO POR FACTURAR
        if approval_status == 'approved':
            return 'servicio_aprobado_por_facturar'

        # SERVICIO ANÁLISIS
        if approval_status == 'pending' and self.is_approval:
            return 'servicio_analisis'

        # SERVICIO EN PROCESO (por defecto)
        return 'servicio_en_proceso'

    @api.model
    def cron_recalculate_situation(self):
        orders = self.search([])
        orders._compute_situation()

    def _domain_payment_term_user(self):
        payment_term_user = self.env.user.payment_term_ids.ids or []
        return [('id', '=', payment_term_user),('company_id', '=', self.company_id.id)]

    payment_term_id = fields.Many2one(
        comodel_name='account.payment.term',
        string="Términos de pago",
        compute='_compute_payment_term_id',
        store=True, readonly=False, precompute=True, check_company=True,  # Unrequired company
        domain=_domain_payment_term_user)

    term_type = fields.Selection(related='payment_term_id.term_type')

    tax_no_fiscal = fields.Boolean(
        string="Aplicar Impuesto No Fiscal?",
        help="Activar para reemplazar los impuestos en las líneas de este pedido con los impuestos no fiscales configurados en el producto."
    )

    logistic_status = fields.Selection(
        string='Estado del Despacho',
        selection=[('in_progress', 'En Proceso'), ('dispach', 'Realizado')],
        compute="_compute_logistic_status",
        store=True
    )

    delivery_request = fields.Boolean(
        string='Requiere Delivery',
        tracking=True,
        copy=False
    )
    
    @api.onchange('tax_no_fiscal')
    def _onchange_tax_no_fiscal(self):
        # Validar que el estado del documento sea 'draft'
        if self.state != 'draft':
            raise UserError("El documento debe estar en estado 'Borrador' para hacer cambios en este botón.")
        
        if self.tax_no_fiscal:
            for line in self.order_line:
                if line.product_id and line.product_id.customer_no_fiscal_taxes_ids:
                    # Asignar el primer impuesto no fiscal
                    line.tax_id = line.product_id.customer_no_fiscal_taxes_ids[:1]
                else:
                    # Si no hay impuesto no fiscal, asignar el impuesto fiscal habitual
                    line.tax_id = line.product_id.taxes_id
        else:
            for line in self.order_line:
                if line.product_id and line.product_id.taxes_id:
                    # Al desactivar, asignar el primer impuesto fiscal
                    line.tax_id = line.product_id.taxes_id[:1]  # Usa el primer impuesto configurado

    @api.depends('picking_ids', 'picking_ids.dispatch_id.state')
    def _compute_logistic_status(self):
        for order in self:
            if not order.picking_ids or all(p.state == 'cancel' for p in order.picking_ids):
                order.logistic_status = False
            elif not order.picking_ids.dispatch_id or all(d.state == 'cancel' for d in order.picking_ids.dispatch_id):
                order.logistic_status = False
            elif all(d.state == 'draft' for d in order.picking_ids.dispatch_id):
                order.logistic_status = False
            elif all(d.state == 'in_progress' for d in order.picking_ids.dispatch_id):
                order.logistic_status = 'in_progress'
            elif any(d.state == 'done' for d in order.picking_ids.dispatch_id):
                order.logistic_status = 'dispach'

    @api.depends('partner_id')
    def _compute_payment_term_id(self):
        for order in self:
            order = order.with_company(order.company_id)
            order.payment_term_id = order.partner_id.property_payment_term_id if order.partner_id.property_payment_term_id.id in self.env.user.payment_term_ids.ids else False

    @api.onchange('branch_id')
    def _onchange_branch_id(self):
        for rec in self:
            rec.journal_id = False

    @api.depends('order_line.fillert')
    def _compute_calculate_fillert(self):
        for rec in self:
            filler = sum(line.fillert for line in rec.order_line)
            rec.fillert = filler
    
    def _prepare_invoice(self):
        invoice_vals = super(SaleOrder, self)._prepare_invoice()
        invoice_vals.update({
            'filler_total' : self.fillert,
            'branch_id' : self.branch_id.id,
            'invoice_payment_term_id':self.payment_term_id.id,
        })
        return invoice_vals

    def action_view_sale_advance_payment_inv(self):
        # raise UserError('Hello')
        # # Verificar si hay aprobaciones
        # approval_requests = self.env['approval.request'].search([('state', '=', 'approved')])
        # if not approval_requests:
        #     raise exceptions.UserError('No hay aprobaciones aprobadas.')
        # # Llamar a la función original si hay aprobaciones
        return super(SaleOrder, self).action_view_sale_advance_payment_inv()

    def validate_almacen(self):
        for rec in self:
            for line in rec.order_line:
                if line.product_id.detailed_type != 'service' and not line.warehouse_ids:
                    raise UserError(f'El Producto {line.product_id.name} no tiene almacenes seleccionados.\n--Elimine la linea agreguelo nuevamente desde *Selec. desde almacén*')

    def is_possible_confirm(self):
        for rec in self:
            return True if rec.approvals_approver_ids.filtered(lambda x: x.required and x.status != 'approved' and x.request_id.request_status != 'cancel') else False

    def action_confirm(self):
        self.validate_almacen()
        res = super(SaleOrder, self).action_confirm()

        warehouse_ids = self.order_line.mapped('warehouse_ids')
        if len(warehouse_ids) > 0:
            first_picking = self.picking_ids[:1]
            group_id = first_picking.group_id if first_picking else None
            self.picking_ids.with_user(SUPERUSER_ID).unlink()
            picking_list = []
            for warehouse in warehouse_ids:
                picking_obj = self.env['stock.picking']
                vals = {
                    'partner_id': self.partner_id.id if not self.partner_shipping_id else self.partner_shipping_id.id,
                    'picking_type_id': warehouse.out_type_id.id,
                    'location_id': warehouse.lot_stock_id.id,
                    'location_dest_id': self.partner_id.property_stock_customer.id,
                    'origin': self.name,
                    'date': fields.Datetime.now(),
                    'group_id': group_id.id,
                    'company_id': self.company_id.id,
                    'state': 'draft',
                }
                # message = "\n".join(f"{key}: {value}" for key, value in vals.items())
                # raise UserError(message)
                picking = picking_obj.with_user(SUPERUSER_ID).create(vals)
                picking_list.append(picking.id)
                lines = self.order_line.filtered(lambda l: warehouse.id in l.warehouse_ids.ids)
                for line in lines:
                    warehouse_info = line.warehouse_info.replace("'", '"')
                    warehouse_info = json.loads(warehouse_info)

                    for info in warehouse_info:
                        if info['warehouse_id'] == warehouse.id:
                            stock_quant = self.env['stock.quant'].search([
                                ('location_id', '=', info['location_id']),
                                ('product_id', '=', info['product_id'])
                            ])
                            disponible = sum(quant.quantity - quant.reserved_quantity for quant in stock_quant)
                            if disponible < info['qty_done']:
                                raise UserError("La cantidad solicitada para el producto: {} es mayor a la disponible en el Almacen: {}".format(
                                    line.product_id.name, self.env['stock.warehouse'].browse(info['warehouse_id']).name))
                            
                            move = self.env['stock.move'].create({
                                'name': line.product_id.name,
                                'product_id': line.product_id.id,
                                'product_uom_qty': info['qty_done'],
                                'product_uom': line.product_id.uom_id.id,
                                'picking_id': picking.id,
                                'location_id': info['location_id'],
                                'location_dest_id': self.partner_id.property_stock_customer.id,
                                'sale_line_id': line.id,
                                'description_picking': line.product_id.name,
                                'origin': line.order_id.name,
                                'quantity': info['qty_done'],
                                'group_id': group_id.id,
                            })
                            move._do_unreserve()
                picking.action_assign()
            self.picking_ids = picking_list
        return res

    @api.depends('is_approval')
    def _compute_approver(self):
        for rec in self:            
            if not rec.is_approval:
                self.approver_ids = []
            else:
                category_obj = self.env['approval.category'].search([('is_order', '!=', 'no'),('company_id','=',rec.company_id.id)], limit=1)
                if category_obj:
                    rec.approver_ids = category_obj.user_ids
                elif category_obj and not category_obj.user_ids:
                    raise ValidationError(
                        "Disculpe no tiene Aprobadores Configurados"
                        "Vaya a Aprobaciones / Configuración / Tipo de aprobación.")

    def action_send_approval(self):
        for order in self:
            # Verificar si ya existe una aprobación en curso o aprobada
            if order.approvals_ids.filtered(lambda r: r.request_status in ['new', 'pending', 'approved']):
                raise ValidationError("Existe una aprobación en curso o ya fue aprobado")

            # Buscar la categoría de aprobación para pedidos de ventas
            category_obj = self.env['approval.category'].search([('is_order', '!=', 'no'),('company_id', '=', order.company_id.id)], limit=1)
            if not category_obj:
                raise ValidationError("No existe una categoría de aprobación configurada para pedidos de ventas.")

            # Crear la solicitud de aprobación
            approval_request = self.env['approval.request'].create({
                'name': f'{category_obj.name} - {order.name}',
                'category_id': category_obj.id,
                'date': fields.Datetime.now(),
                'request_owner_id': self.env.user.id,
                'partner_id': order.partner_id.id,
                'order_id': order.id,
            })
            approval_request.action_confirm()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Aprobación Registrada'),
                'message': _('La solicitud de aprobación se ha registrado correctamente.'),
                'sticky': False,  # Si es True, la notificación no desaparece hasta que el usuario la cierre
                'next': {
                    'type': 'ir.actions.act_window_close',
                }
            }
        }

    def action_cancel(self):
        res = super(SaleOrder, self).action_cancel()
        for rec in self:
            if rec.approvals_ids:
                for approval in rec.approvals_ids.filtered(lambda l: l.request_status != 'cancel'):
                    approval.write({'request_status': 'cancel'})
                    for approver in approval.approver_ids:
                        approver.write({'status': 'cancel'})
        return res

    @api.depends('payment_term_id')
    def _compute_is_approval(self):
        for rec in self:
            rec.is_approval = True if rec.payment_term_id.term_type == 'credit' else False

    def action_check_approvals_and_open_wizard(self):
        for rec in self:
            if rec.is_approval:
                if not rec.approvals_ids or not rec.approvals_ids.filtered(lambda l: l.request_status in ['new','pending','approved']):
                    raise ValidationError("Disculpe!!! Debe solicitar aprobación.")
                else:
                    if self.is_possible_confirm():
                        raise ValidationError("Existen aprobadores requeridos pendientes por aprobar.")
                    elif not rec.approvals_ids.filtered(lambda l: l.request_status == 'approved'):
                        raise ValidationError("Existen aprobaciones pendientes.")
        return self.env.ref('sale.action_view_sale_advance_payment_inv').read()[0]

class SaleMassCancelOrders(models.TransientModel):
    _inherit = "sale.mass.cancel.orders"

    @api.model
    def action_cancel_orders(self):
        # Llama a la acción original
        super(SaleMassCancelOrders, self).action_cancel_orders()
        
        # Obtén las órdenes de venta seleccionadas
        sale_orders = self.env['sale.order'].browse(self._context.get('active_ids', []))
        
        # Itera sobre las órdenes y procesa los approvals_ids
        for order in sale_orders:
            if order.approval_ids:  # Suponiendo que tienes una relación con approval_ids
                approvals = order.approval_ids
                for approval in approvals:
                    if approval.request_status not in ('cancel', 'done'):  # Asegúrate de no duplicar cancelaciones
                        approval.write({'request_status': 'cancel'})