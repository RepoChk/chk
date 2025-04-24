# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, date
# from odoo.exceptions import Warning, UserError
from odoo.exceptions import UserError, ValidationError

class MaterialPurchaseRequisition(models.Model):    
    _name = 'material.purchase.requisition'
    _description = 'Purchase Requisition'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'id desc'
    
    def unlink(self):
        for rec in self:
            if rec.state not in ('draft', 'cancel', 'reject'):
                raise UserError(_('You can not delete Purchase Requisition which is not in draft or cancelled or rejected state.'))
        return super(MaterialPurchaseRequisition, self).unlink()
    
    name = fields.Char(
        string='Number',
        index=True,
        readonly=True,
        required=True, 
        copy=False,
        default='/'
    )
    state = fields.Selection([
        ('draft', 'Borrador'), 
        ('confirmed', 'En Curso'), 
        ('approve', 'Aprobado'),
        ('done', 'Realizado'), 
        ('cancel', 'Cancelado')
        ],
        default='draft',
        tracking=True
    )
    request_date = fields.Date(
        string='Requisition Date',
        default=lambda self: fields.Date.context_today(self),
        required=True,
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        required=True,
    )

    user_id = fields.Many2one(
        'res.users',
        default=lambda self: self.env['res.users'].search([('id', '=', self.env.uid)], limit=1),
        required=True,
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Entrega a'
    )
    
    approve_manager_id = fields.Many2one(
        'hr.employee',
        string='Department Manager',
        readonly=True,
        copy=False,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañia',
        default=lambda self: self.env.company,
        required=True,
        copy=True,
    )
    location_id = fields.Many2one(
        'stock.location',
        string='Source Location',
        compute="_compute_location_id",
        store=True,
        copy=True,
    )
    requisition_line_ids = fields.One2many(
        'material.purchase.requisition.line',
        'requisition_id',
        string='Purchase Requisitions Line',
        copy=True,
        tracking=True
    )
    date_end = fields.Date(
        string='Requisition Deadline', 
        readonly=True,
        help='Last date for the product to be needed',
        copy=True,
    )
    date_done = fields.Date(
        string='Date Done', 
        readonly=True, 
        help='Date of Completion of Purchase Requisition',
    )
    managerapp_date = fields.Date(
        string='Department Approval Date',
        readonly=True,
        copy=False,
    )
    manareject_date = fields.Date(
        string='Department Manager Reject Date',
        readonly=True,
    )
    userreject_date = fields.Date(
        string='Rejected Date',
        readonly=True,
        copy=False,
    )
    userrapp_date = fields.Date(
        string='Approved Date',
        readonly=True,
        copy=False,
    )
    receive_date = fields.Date(
        string='Received Date',
        readonly=True,
        copy=False,
    )
    reason = fields.Text(
        string='Reason for Requisitions',
        required=False,
        copy=True,
        tracking=True
    )
    delivery_picking_id = fields.Many2one(
        'stock.picking',
        string='Internal Picking',
        readonly=True,
        copy=False,
    )
    order_partner_id = fields.Many2many(
        'res.partner',
        tracking=True
    )
    
    picking_count = fields.Integer(
        string='Contador de picking', compute='_compute_picking_ids'
    )

    @api.depends('delivery_picking_id')
    def _compute_picking_ids(self):
        for item in self:
            item.picking_count = len(item.delivery_picking_id)

    user_responsible_id = fields.Many2one(
        'res.users',
        string='Requisition Responsible',
        copy=True,
    )

    confirm_date = fields.Date(
        string='Confirmed Date',
        readonly=True,
        copy=False,
    )
    
    priority = fields.Selection(
        string='Prioridad', 
        selection=[
            ('no', 'No asignada'), 
            ('very_low', 'Very Low'), 
            ('low', 'Low'), 
            ('meddium', 'Meddium'), 
            ('high', 'High'), 
            ('very_high', 'Muy Alta')
        ], 
        default="no"
    )
 
    requisition_type = fields.Selection(
        string='Tipo de Requisición', 
        selection=[
            ('internal', 'Almacén'), 
            ('purchase', 'Compra de Productos'), 
            ('service_purchase', 'Compra de Servicios'), 
            ('cxp', 'CxP - Pago directo')
        ]
    )

    invoice_ids = fields.One2many(
        'account.move',
        'custom_requisition_id',
        string='Facturas',
    )

    invoice_count = fields.Integer(
        string='Contador de requisiciones', compute='_compute_invoice_ids'
    )

    approvals_approver_ids = fields.Many2many('approval.approver', string='Aprobaciones', compute='_compute_approvals_approver_ids')

    department_user_id = fields.Many2one(
        'res.users',
        string='Gerente',
        readonly=False,
    )

    @api.onchange('department_id')
    def _onchange_department_id(self):
        for rec in self:
            if rec.department_id:
                rec.department_user_id = rec.department_id.gc_user_id
            else:
                rec.department_user_id = False

    currency_id = fields.Many2one('res.currency', required=True, default=lambda self: self.env.company.currency_id.id)
    currency_id_dif = fields.Many2one('res.currency', required=True, default=lambda self: self.env.company.currency_id_dif.id)
    amount_total = fields.Monetary(string='Importe total', currency_field='currency_id', tracking=True)
    amount_currency_total = fields.Monetary(string='Importe en moneda.', currency_field='currency_id_dif', tracking=True)
    rate = fields.Float(string='Tasa', store=True, readonly=False, default=lambda self: self._get_default_tasa_cambio(), tracking=True, digits='Dual_Currency_rate')
    no_require_invoice = fields.Boolean(string='No requiere Factura', default=False, tracking=True)

    @api.onchange('amount_total', 'rate')
    def _onchange_amount_total(self):
        for rec in self:
            rec.amount_currency_total = rec.amount_total / rec.rate or 0

    @api.onchange('amount_currency_total', 'rate')
    def _onchange_amount_currency_total(self):
        for rec in self:
            rec.amount_total = rec.amount_currency_total * rec.rate or 0

    def _get_default_tasa_cambio(self):
        dolar = self.env['res.currency'].search([('name', '=', 'USD')])
        tasa = dolar.inverse_company_rate
        return tasa

    @api.depends('approvals_ids', 'cxp_approvals_ids')
    def _compute_approvals_approver_ids(self):
        for rec in self:
            approver_ids = self.env['approval.approver']
            if rec.requisition_type == 'cxp':
                if rec.approvals_ids:
                    approver_ids |= rec.approvals_ids.mapped('approver_ids')
                if rec.cxp_approvals_ids:
                    approver_ids |= rec.cxp_approvals_ids.mapped('approver_ids')
            else:
                if len(rec.approvals_ids) >= 1:
                    approver_ids |= rec.approvals_ids.mapped('approver_ids')

            # Ordenar approver_ids por fecha de creación de más reciente a más antigua
            approver_ids = approver_ids.sorted(lambda r: r.create_date, reverse=True)

            rec.approvals_approver_ids = approver_ids

    @api.depends('invoice_ids')
    def _compute_invoice_ids(self):
        for item in self:
            account_move = self.env['account.move'].search([
                ('custom_requisition_id', '=', item.id)
            ])
            item.invoice_count = len(account_move)

    purchase_order_ids = fields.One2many(
        'gc.purchase.requisition.line',
        'requisition_id',
        string='Purchase Ordes',
    )

    purchase_count = fields.Integer(
        string='Contador de requisiciones', compute='_compute_purchase_ids'
    )

    @api.depends('purchase_order_ids')
    def _compute_purchase_ids(self):
        for item in self:
            purchase_orders = self.env['gc.purchase.requisition.line'].search([
                ('requisition_id', '=', item.id)
            ])
            item.purchase_count = len(purchase_orders)

    custom_picking_type_id = fields.Many2one(
        'stock.picking.type',
        string='Picking Type',
        copy=False,
    )

    is_approval = fields.Boolean(
        string="Tiene Aprobación", default=True,
    )

    approvals_ids = fields.One2many(
        'approval.request', 
        'mp_requisition_id', 
        string='Aprobaciones',
    )

    cxp_approvals_ids = fields.One2many(
        'approval.request', 
        'cxp_id', 
        string='Aprobaciones de CXP', 
    )

    combined_approvals = fields.Many2many(
        'approval.request', 
        string='Aprobaciones',
        compute='_compute_combined_approvals'
    )

    @api.depends('approvals_ids', 'cxp_approvals_ids')
    def _compute_combined_approvals(self):
        for rec in self:
            approver_ids = []
            
            if rec.requisition_type == 'cxp':
                if rec.approvals_ids:
                    approver_ids.extend(rec.approvals_ids)
                if rec.cxp_approvals_ids:
                    approver_ids.extend(rec.cxp_approvals_ids)
            else:
                if len(rec.approvals_ids) >= 1:
                    approver_ids.extend(rec.approvals_ids)
            
            # Ordenar los IDs por create_date de mayor a menor
            if approver_ids:
                sorted_approvals = sorted(approver_ids, key=lambda x: x.create_date, reverse=True)
                rec.combined_approvals = [approval.id for approval in sorted_approvals]
            else:
                rec.combined_approvals = []

    cxp_approver_ids = fields.Many2many(
        'res.users', 
        'cxp_res_user_rel',
        string='Aprobadores de pagos directos', 
        readonly=True, 
        compute='_cxp_compute_approver', 
        store=True
    )

    approver_ids = fields.Many2many(
        'res.users', 
        string='Aprobadores', 
        readonly=True, 
        default=lambda x: x.env['res.users'].search([('id', '=', x.env.uid)]).approving_leader_req_ids.ids,
        store=True
    )
    
    approver_analytic_ids = fields.Many2many(
        'res.users', 
        relation='gc_material_purchase_requitions_approver_analytic', 
        string='Aprobadores de Cuenta Analítica', 
        readonly=True, 
        compute='_compute_approver_analytic', 
        store=True
    )

    remove_approval = fields.Boolean(
        compute='_compute_remove_approval', store=True
    )

    manager_approval = fields.Selection(
        [('approver', 'Es aprobador'), ('required', 'Es aprobador requerido')], 
        compute='_compute_manager_approval', 
    )

    @api.depends('requisition_type')
    def _compute_manager_approval(self):
        for rec in self:
            manager_approval = False
            if rec.requisition_type == 'cxp':
                category_obj = self.env['approval.category'].search([('is_cxp', '!=', 'no')], limit=1)
                if category_obj:
                    manager_approval = category_obj.manager_approval
            rec.manager_approval = manager_approval

    @api.depends('approver_ids')
    def _compute_remove_approval(self):
        self.remove_approval = self.env.user.remove_approval

    @api.depends('is_approval')
    def _compute_approver_analytic(self):
        for rec in self:
            category_obj = self.env['approval.category'].search([('has_analytic_request', '!=', 'no'),('company_id', '=', rec.company_id.id)], limit=1)
            if category_obj:
                rec.approver_analytic_ids = category_obj.user_ids
            elif category_obj and not category_obj.user_ids:
                raise ValidationError(
                    "Disculpe no tiene Aprobadores Configurados"
                    "Vaya a Aprobaciones / Configuración / Tipo de aprobación.")

    @api.depends('custom_picking_type_id')
    def _compute_location_id(self):
        for picking in self:
            if picking.state != 'draft':
                continue
            picking = picking.with_company(picking.company_id)
            if picking.custom_picking_type_id:
                if picking.custom_picking_type_id.default_location_src_id:
                    location_id = picking.custom_picking_type_id.default_location_src_id.id

                picking.location_id = location_id

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            company_id = vals.get('company_id', self.env.company.id)
            vals['name'] = self.env['ir.sequence'].with_company(company_id).next_by_code('purchase.requisition.seq') or '/'
        return super(MaterialPurchaseRequisition, self).create(vals)


    def requisition_confirm(self):
        for rec in self:
            rec.confirm_date = fields.Date.today()
            rec.state = 'confirmed'

    def approvals_analityc_request(self):
        for rec in self:
            # Buscar la categoría de aprobación de la cuenta analitica
            category_analytic_obj = self.env['approval.category'].search([('has_analytic_request', '!=', 'no')], limit=1)
            if not category_analytic_obj.user_ids:
                raise ValidationError(
                    "Disculpe no tiene Aprobadores de Cuentas Analiticas Configurados"
                    "Vaya a Aprobaciones / Configuración / Tipo de aprobación.")

            # Crear la solicitud de aprobación de requisición
            analytic_approval_request = self.env['approval.request'].with_context(mng_id=rec.department_user_id.id).create({
                'name': category_analytic_obj.name + ' ' + rec.name,
                'category_id': category_analytic_obj.id,
                'date': datetime.now(),
                'request_owner_id': self.env.user.id,
                'mp_requisition_id': rec.id,
                'reason': rec.reason,
                'request_status': 'pending'
            })
            analytic_approval_request.action_confirm()

    def approvals_requisition_request(self):
        for rec in self:
            # Buscar la categoría de aprobación de la requisición
            category_obj = self.env['approval.category'].search([('has_requisition_request', '!=', 'no')], limit=1)
            if not category_obj:
                raise ValidationError("No existe una categoría de aprobación configurada para la Requisiciones.")

            # Crear la solicitud de aprobación de requisición
            approval_request = self.env['approval.request'].with_context(mng_id=rec.department_user_id.id).create({
                'name': category_obj.name + ' ' + rec.name,
                'category_id': category_obj.id,
                'date': datetime.now(),
                'request_owner_id': self.env.user.id,
                'mp_requisition_id': rec.id,
                'reason': rec.reason,
                'request_status': 'pending'
            })

            for item in rec.approver_ids:
                self.env['approval.approver'].create({
                    'user_id': item.id,
                    'request_id': approval_request.id,
                    'status': 'pending'
            })
            approval_request.action_confirm()
        
    def approvals_cxp_request(self):
        for rec in self:
            # Buscar la categoría de aprobación para pagos directos (CxP)
            category_obj = self.env['approval.category'].search([('is_cxp', '!=', 'no'),('company_id', '=', rec.company_id.id)], limit=1)
            if not category_obj:
                raise ValidationError("No existe una categoría de aprobación configurada para pagos directos (CxP).")

            # Crear la solicitud de aprobación
            approval_request = self.env['approval.request'].with_context(mng_id=rec.department_user_id.id).create({
                'name': f'{category_obj.name} - {rec.name}',
                'category_id': category_obj.id,
                'date': fields.Datetime.now(),
                'request_owner_id': self.env.user.id,
                'cxp_id': rec.id,
                'mp_requisition_id': rec.id,
                'request_status': 'pending',
            })

            for approver in approval_request.approver_ids:
                approver.write({'status': 'pending'})
                # if approver.is_high_payment_approver:
                #     approver.write({'status': 'required'})
            
            # self.approvals_manager_approval_request(approval_request)

    def approvals_manager_approval_request(self, approval_request):
        # Buscamos a los lideres aprobadores en el usuario actual
        for rec in self:
            if rec.manager_approval and rec.department_user_id:
                user = rec.department_user_id.user_id or False
                if not user:
                    raise ValidationError("El gerente no tiene un usuario relacionado\n - Dirijase a Empleados / Ajustes de RR. HH. / Usuario relacionado")
                else:
                    requerido = True if rec.manager_approval == 'required' else False
                    self.env['approval.approver'].create({
                        'user_id': user.id,
                        'request_id': approval_request.id,
                        'status': 'pending',
                        'required': requerido,
                    })

    def approvals_request(self):
        for rec in self:
            if not rec.requisition_line_ids:
                raise UserError(_('Por favor, cree algunas líneas de requisición.'))
            
            if rec.approvals_ids.filtered(lambda r: r.request_status in ['new', 'pending', 'approved']):
                raise ValidationError("Existe una aprobación en curso o ya fue aprobado")

            self.approvals_requisition_request()
            self.approvals_analityc_request()
            self.requisition_confirm()

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

    @api.depends('is_approval')
    def _cxp_compute_approver(self):
        for rec in self:
            category_obj = self.env['approval.category'].search([('is_cxp', '!=', 'no'),('company_id', '=', rec.company_id.id)], limit=1)
            if category_obj:
                rec.cxp_approver_ids = category_obj.approver_ids.user_id.ids
            elif category_obj and not category_obj.approver_ids:
                raise ValidationError(
                    "Disculpe no tiene Aprobadores Configurados"
                    "Vaya a Aprobaciones / Configuración / Tipo de aprobación.")

    def send_approval_cxp(self):
        for rec in self:
            # Verificar si ya existe una aprobación en curso o aprobada
            if rec.cxp_approvals_ids.filtered(lambda r: r.request_status in ['new', 'pending']):
                raise ValidationError("Existe una aprobación de pago directo en curso")

            if rec.cxp_approvals_ids.filtered(lambda r: r.request_status == 'approved'):
                raise ValidationError("Ya fue aprobado el pago directo")
            # Enviamos la solicitud de cuenatas analiticas
            self.approvals_analityc_request()

            # Enviamos la solicitud de aprobación de pago directo
            self.approvals_cxp_request()

            self.requisition_confirm()
        
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

    def is_possible_confirm(self):
        for rec in self:
            return True if rec.approvals_approver_ids.filtered(lambda x: x.required and x.status != 'approved' and x.request_id.request_status != 'cancel') else False
    
    def reset_draft(self):
        for rec in self:
            if not self.check_creator_user():
                raise UserError('Solo el Usuario que creó la Requición puede cancelarla.')
            if rec.approvals_ids:
                for approval in rec.approvals_ids.filtered(lambda l: l.request_status != 'cancel'):
                    approval.write({'request_status': 'cancel'})
                    for approver in approval.approver_ids:
                        approver.write({'status': 'cancel'})
            rec.state = 'draft'

    @api.model
    def _prepare_pick_vals(self, line=False, stock_id=False):
        pick_vals = {
            'product_id' : line.product_id.id,
            'product_uom_qty' : line.qty,
            'product_uom' : line.uom.id,
            'location_id' : self.location_id.id,
            'partner_id' : self.partner_id.id,
            'location_dest_id' : self.partner_id.property_stock_customer.id,
            'name' : line.product_id.name,
            'picking_type_id' : self.custom_picking_type_id.id,
            'picking_id' : stock_id.id,
            'custom_requisition_line_id' : line.id,
            'analytic_distribution':  line.analytic_distribution,
            'company_id' : line.requisition_id.company_id.id,
        }
        return pick_vals

    @api.model
    def _prepare_po_line(self, line=False, purchase_order=False):
        seller = line.product_id._select_seller(
                partner_id=self._context.get('partner_id'), 
                quantity=line.qty,
                date=purchase_order.date_order and purchase_order.date_order.date(), 
                uom_id=line.uom
                )
        po_line_vals = {
                'product_id': line.product_id.id,
                'name':line.product_id.name,
                'product_qty': line.qty,
                'product_uom': line.uom.id,
                'date_planned': fields.Date.today(),
                 # 'price_unit': line.product_id.standard_price,
                'price_unit': seller.price or line.product_id.standard_price or 0.0,
                'order_id': purchase_order.id,
                 # 'account_analytic_id': self.analytic_account_id.id,
                'analytic_distribution': line.analytic_distribution,
                'custom_requisition_line_id': line.id
        }
        return po_line_vals

    @api.model
    def _prepare_invoice_line(self, line=False, invoice=False):
        seller = line.product_id._select_seller(
                partner_id=self._context.get('partner_id'), 
                quantity=line.qty,
                uom_id=line.uom
                )
        invoice_line_vals = {
            'move_id': invoice.id,
            'product_id': line.product_id.id,
            'quantity': line.qty,
            'name': line.description,
            'custom_requisition_line_id': line.id,
            'analytic_distribution': line.analytic_distribution
        }
        return invoice_line_vals

    # @api.multi
    def request_stock(self):
        if self.is_approval:
            # Obtener todas las solicitudes de aprobación
            approvals = self.approvals_ids
            approved_count = len(approvals.filtered(lambda r: r.request_status == 'approved'))
            pending_count = len(approvals.filtered(lambda r: r.request_status in ['new', 'pending']))

            if self.is_possible_confirm():
                raise ValidationError("Existen aprobadores requeridos que no han aprobado aún")
            
            # Si hay al menos 2 aprobaciones, permitir continuar
            if approved_count == 0:
                raise ValidationError("Aún no ha sido aprobado por ninguno de los aprobadores")
            # Si hay solicitudes pendientes, mostrar mensaje
            # elif pending_count > 0:
            #     raise ValidationError("Las aprobaciones deben estar aceptadas para validar la Requisición.")
            # Si todas están canceladas o no hay suficientes aprobadas
            # else:
            #     raise ValidationError("Se requieren al menos 2 aprobaciones aceptadas para validar la Requisición.")      

        stock_obj = self.env['stock.picking']
        move_obj = self.env['stock.move']
        for rec in self:
            if not rec.requisition_line_ids:
                raise UserError(_('Por favor, cree algunas líneas de requisición.'))
            if rec.requisition_type =='internal':
                if not rec.location_id.id:
                    raise UserError(_('Seleccione Ubicación de Origen en los detalles del picking.'))
                if not rec.custom_picking_type_id.id:
                    raise UserError(_('Seleccione Tipo de picking en los detalles del picking.'))
                if not rec.partner_id.id:
                    raise UserError(_('Seleccione a quien Entrega en los detalles de picking.'))
                picking_vals = {
                        'location_id' : rec.location_id.id,
                        'partner_id' : rec.partner_id.id,
                        'location_dest_id' : rec.partner_id.property_stock_customer.id,
                        'picking_type_id' : rec.custom_picking_type_id.id,#internal_obj.id,
                        'note' : rec.reason,
                        'custom_requisition_id' : rec.id,
                        'origin' : rec.name,
                        'company_id' : rec.company_id.id,
                        
                    }
                stock_id = stock_obj.sudo().create(picking_vals)
                delivery_vals = {
                        'delivery_picking_id' : stock_id.id,
                    }
                rec.write(delivery_vals)

                for line in rec.requisition_line_ids:
                    if rec.requisition_type =='internal':
                        pick_vals = rec._prepare_pick_vals(line, stock_id)
                        move_id = move_obj.sudo().create(pick_vals)

    def request_purchase_service(self):
        if self.is_approval:
            # Obtener todas las solicitudes de aprobación
            approvals = self.approvals_ids
            approved_count = len(approvals.filtered(lambda r: r.request_status == 'approved'))
            pending_count = len(approvals.filtered(lambda r: r.request_status in ['new', 'pending']))
            
            # Si hay al menos 2 aprobaciones, permitir continuar
            if approved_count >= 2:
                pass
            # Si hay solicitudes pendientes, mostrar mensaje
            elif pending_count > 0:
                raise ValidationError("Las aprobaciones deben estar aceptadas para validar la Requisición.")
            # Si todas están canceladas o no hay suficientes aprobadas
            else:
                raise ValidationError("Se requieren al menos 2 aprobaciones aceptadas para validar la Requisición.")  
                    

       # Validar que no se creen más cotizaciones si ya se alcanzó la cantidad solicitada
        for line in self.requisition_line_ids:
            if line.qty_ordered == line.qty:
                raise UserError(_(
                    'No se pueden crear más cotizaciones. '
                    'La cantidad solicitada (%s) ya ha sido ordenada completamente '
                    'para el producto "%s"'
                ) % (line.qty, line.product_id.name))

        purchase_obj = self.env['purchase.order']
        purchase_line_obj = self.env['purchase.order.line']
        purchase_requisition_line_obj = self.env['gc.purchase.requisition.line']        

        for rec in self:
            po_dict = {}
            for line in rec.requisition_line_ids:
                if rec.requisition_type in ['purchase', 'service_purchase']:
                    if not rec.order_partner_id:
                        raise UserError(_('Por favor, introduzca al menos un proveedor en las Líneas de Requisición'))
                    
                    # Crear o reutilizar la orden de compra
                    for partner in rec.order_partner_id:
                        if partner not in po_dict:
                            po_vals = {
                                'partner_id': partner.id,
                                'user_id': rec.env.user.id,
                                'currency_id': rec.env.user.company_id.currency_id.id,
                                'date_order': fields.Date.today(),
                                'company_id': rec.company_id.id,
                                'is_requisition': True,
                                'origin': rec.name,
                            }
                            purchase_order = purchase_obj.create(po_vals)
                            po_dict.update({partner: purchase_order})
                        else:
                            purchase_order = po_dict.get(partner)

                        po_line_vals = rec.with_context(partner_id=partner)._prepare_po_line(line, purchase_order)
                        purchase_line_obj.sudo().create(po_line_vals)
                        purchase_requisition_line_obj.sudo().create({'requisition_id': rec.id, 'purchase_order_id': purchase_order.id})

    def action_invoice(self):
        if self.is_approval:
            # Obtener todas las solicitudes de aprobación
            approvals = self.approvals_ids
            approved_count = len(approvals.filtered(lambda r: r.request_status == 'approved'))
            pending_count = len(approvals.filtered(lambda r: r.request_status in ['new', 'pending']))

            if self.is_possible_confirm():
                raise ValidationError("Hay validaciones pendientes por aprobadores requeridos")
            
            if approved_count == 0:
                raise ValidationError("No ha sido aprobado por ninguno de los aprobadores")
            
        account_move_obj = self.env['account.move']
        account_move_line_obj = self.env['account.move.line']
        
        for rec in self:
            invoice_dict = {}
            if not rec.requisition_line_ids:
                raise UserError(_('Por favor, cree las líneas de requisición.'))

            for line in rec.requisition_line_ids:
                if rec.requisition_type == 'cxp':
                    if not rec.order_partner_id:
                        raise UserError(_('Por favor, introduzca al menos un proveedor en las Líneas de Requisición'))

                    for partner in rec.order_partner_id:
                        if partner not in invoice_dict:
                            invoice_vals = {
                                'state': 'draft',
                                'move_type': 'in_invoice',
                                'partner_id': partner.id,
                                'invoice_date': fields.Date.context_today(self),
                                'custom_requisition_id':rec.id,
                            }
                            invoice = account_move_obj.create(invoice_vals)
                            invoice_dict.update({partner: invoice})
                        else:
                            invoice = invoice_dict.get(partner)

                        invoice_line_vals = rec.with_context(partner_id=partner)._prepare_invoice_line(line, invoice)
                        account_move_line_obj.sudo().create(invoice_line_vals)    
    
    def action_done(self):
        for rec in self:
            rec.state = 'done'

    def check_creator_user(self):
        for rec in self:
            if rec.create_uid.id != self.env.uid:
                return False
        return True
 
    def action_cancel(self):
        for rec in self:
            if not self.check_creator_user():
                raise UserError('Solo el Usuario que creó la Requición puede cancelarla.')
            # Verificar si hay órdenes de compra vinculadas
            if (rec.requisition_type in ['purchase', 'service_purchase']):
                purchase = self.env['gc.purchase.requisition.line'].search([('requisition_id', '=', rec.id), ('purchase_order_id.state', '!=', 'cancel')])
                if len(purchase) > 0:
                    raise UserError(_('La Orden de Compra debe estar cancelada para poder cancelar la Requisición.'))
                
            # Verificar si hay facturas vinculadas
            if rec.requisition_type == 'cxp':
                invoice = account_move = self.env['account.move'].search([('custom_requisition_id', '=', rec.id), ('state', '!=', 'cancel')])
                if len(invoice) > 0:
                    raise UserError(_('La Factura debe estar cancelada para poder cancelar la Requisición.'))
                else:
                    if rec.combined_approvals:
                        for approval in rec.combined_approvals.filtered(lambda l: l.request_status != 'cancel'):
                            approval.write({'request_status': 'cancel'})
                            for approver in approval.approver_ids:
                                approver.write({'status': 'cancel'})
                
            # Verificar si hay traslados vinculados
            if rec.requisition_type == 'internal':
                picking = self.env['stock.picking'].search([('custom_requisition_id', '=', rec.id), ('state', '!=', 'cancel')])
                if len(picking) > 0:
                    raise UserError(_('El picking debe estar cancelado para poder cancelar la Requisición.'))
                
            rec.state = 'cancel'
    
    # @api.onchange('user_id')
    # def set_department(self):
    #     for rec in self:
    #         rec.department_id = rec.user_id.sudo().partner_id.employee_ids.department_id.id

    def show_picking(self):
        self.ensure_one()
        res = self.env['ir.actions.act_window']._for_xml_id('stock.action_picking_tree_all')
        res['domain'] = str([('custom_requisition_id','=',self.id)])
        return res
    
    def get_requisition_type(self):
        requisition_type_mapping = {
            'internal': 'Almacén',
            'purchase': 'Compra de productos',
            'service_purchase': 'Compra de servicios',
            'cxp': 'CxP - Pago directo',
        }
        return requisition_type_mapping.get(self.requisition_type, '')
    
    def get_state_requisition(self):
        state_mapping = {
            'draft': 'Borrador',
            'confirmed': 'En Curso',
            'approve': 'Aprobado',
            'done': 'Realizado',
            'cancel': 'Cancelado'
        }
        return state_mapping.get(self.state, '') 
    

    def action_show_po(self):
        self.ensure_one()
        purchase_action = self.env['ir.actions.act_window']._for_xml_id('purchase.purchase_rfq')
        purchase_action['domain'] = str([('gc_requisition_ids.requisition_id','=',self.id)])
        return purchase_action
    
    def action_view_invoice(self):
        self.ensure_one()
        account_action = self.env['ir.actions.act_window']._for_xml_id('account.action_move_in_invoice_type')
        account_action['domain'] = str([('custom_requisition_id','=',self.id)])
        return account_action
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

