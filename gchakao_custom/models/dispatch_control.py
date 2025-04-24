# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class DispatchControl(models.Model):
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _name = "dispatch.control"
    _description = 'Control de Despachos'
    _rec_name = 'name'
    _order = 'name DESC'

    name = fields.Char(
        string='Name',
        required=True,
        default=lambda self: _('New'),
        copy=False,
        readonly=True
    )
    exclude_kpi = fields.Boolean(
        string='Excluir de KPI', 
        default=False,
        tracking=True
    )
    user_id = fields.Many2one(
        'res.users', string='Responsable', tracking=True, 
        default=lambda self: self.env.user
    )
    company_id = fields.Many2one(
        'res.company', string="Company", required=True, readonly=True,
        index=True, default=lambda self: self.env.company
    )
    picking_ids = fields.One2many(
        'stock.picking', 'dispatch_id', string='Transfers',
        domain="[('id', 'in', allowed_picking_ids)]",
        help='List of transfers associated to this dispatch'
    )
    show_check_availability = fields.Boolean(
        compute='_compute_move_ids',
        string='Show Check Availability'
    )
    allowed_picking_ids = fields.One2many(
        'stock.picking', 
        compute='_compute_allowed_picking_ids'
    )
    move_ids = fields.One2many(
        'stock.move', string="Stock moves", 
        compute='_compute_move_ids'
    )
    move_line_ids = fields.One2many(
        'stock.move.line', string='Stock move lines',
        compute='_compute_move_ids', inverse='_set_move_line_ids'
    )
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('in_progress', 'En progreso'),
        ('done', 'Realizado'),
        ('cancel', 'Cancelado')], default='draft',
        store=True,
        copy=False, tracking=True, required=True, readonly=True, index=True
    )

    vehicle_id = fields.Many2one(
        'fleet.vehicle', string='Vehículo', tracking=True
    )
    driver_id = fields.Many2one(
        'res.partner', string='Conductor'
    )
    vehicle_filler = fields.Float(
        string='Filler del Vehículo', related='vehicle_id.vehicle_filler', store=True,
    )
    vehicle_weight = fields.Float(
        string='Capacidad de Peso', related='vehicle_id.vehicle_weight', store=True,
    )
    loaded_filler = fields.Float(
        string='Filler Cargado', compute="_calculate_loaded_filler", store=True
    )
    loaded_weight = fields.Float(
        string='Peso de la Carga', compute="_calculate_loaded_weight", store=True
    )
    date_start = fields.Datetime(
        string='Fecha Desde',
        tracking=True
    )
    date_end = fields.Datetime(
        string='Fecha Hasta',
        tracking=True
    )
    delivery_date = fields.Datetime(
        'Fecha de Llegada',
        tracking=True
    )
    type_vehicle = fields.Selection(
        [('internal', 'Interno'), ('external', 'Externo')], related='vehicle_id.type_vehicle', string='Tipo de Vehículo'
    )
    km_estimate = fields.Float(
        string='Kilómetros Estimados', tracking=True
    )
    disel_consumed = fields.Float(
        string='Consumo de Gasoil', tracking=True
    )
    currency_id_dif = fields.Many2one(
        "res.currency", related="company_id.currency_id_dif", store=True
    )
    coste_km = fields.Monetary(
        string='Costo por Kilómetro', related='vehicle_id.coste_km', currency_field='currency_id_dif', store=True,
    )
    total_value_road = fields.Monetary(
        string='Valor Total de la Ruta', 
        compute='_compute_total_value_road',
        currency_field='currency_id_dif',
        store=True
    )
    road_ids = fields.One2many(
        'dispatch.control.road', 
        'dispatch_control_id', 
        string='Rutas'
    )
    initial_km = fields.Float(
        string="Kilometraje inicial",
        tracking=True
    )
    end_km = fields.Float(
        string="Kilometraje Final",
        tracking=True
    )
    km_total = fields.Float(
        string="",
        tracking=True,
        compute="_compute_km_total", store=True,
    )
    available_filler = fields.Float(
        string="Capacidad Filler Disponible",
        compute="_compute_available_filler"
    )
    available_weight = fields.Float(
        string="Capacidad de Peso Disponible",
        compute="_compute_available_weight"
    )

    @api.depends('vehicle_filler', 'loaded_filler')
    def _compute_available_filler(self):
        for rec in self:
            rec.available_filler = rec.vehicle_filler - rec.loaded_filler

    @api.depends('vehicle_weight', 'loaded_weight')
    def _compute_available_weight(self):
        for rec in self:
            rec.available_weight = rec.vehicle_weight - rec.loaded_weight

    @api.depends('company_id', 'state')
    def _compute_allowed_picking_ids(self):
        allowed_picking_states = ['waiting', 'confirmed', 'assigned', 'done']

        for dispatch in self:
            domain_states = list(allowed_picking_states)
            # Allows to add draft pickings only if batch is in draft as well.
            if dispatch.state == 'draft':
                domain_states.append('draft')
            domain = [
                ('state', 'in', domain_states),
                ('dispatch_assigned', '=', False),
                ('picking_type_id.code', '=', 'outgoing'),
                ('sale_id.logistic_active', '=', True),
            ]
            dispatch.allowed_picking_ids = self.env['stock.picking'].search(domain)

    @api.depends('picking_ids', 'picking_ids.move_line_ids', 'picking_ids.move_ids', 'picking_ids.move_ids.dispatch_status')
    def _compute_move_ids(self):
        for dispatch in self:
            dispatch.move_ids = dispatch.picking_ids.move_ids
            dispatch.move_line_ids = dispatch.picking_ids.move_line_ids
            dispatch.show_check_availability = any(m.dispatch_status not in ['assigned'] for m in dispatch.move_ids)

    def _set_move_line_ids(self):
        new_move_lines = self[0].move_line_ids
        for picking in self.picking_ids:
            old_move_lines = picking.move_line_ids
            picking.move_line_ids = new_move_lines.filtered(lambda ml: ml.picking_id.id == picking.id)
            move_lines_to_unlink = old_move_lines - new_move_lines
            if move_lines_to_unlink:
                move_lines_to_unlink.unlink()


    @api.onchange('vehicle_id')
    def _onchange_driver(self):
        for rec in self:
            rec.driver_id = rec.vehicle_id.driver_id

    @api.onchange('date_end')
    def _onchange_date_to(self):
        if self.date_start:
            if self.date_end:
                if self.date_end < self.date_start:
                    raise UserError(
                        "El rango de fecha establecido no es valido.\n"
                        "Por favor ingrese una fecha final que sea mayor a la inicial.")
    
    @api.depends('picking_ids','vehicle_filler')
    def _calculate_loaded_filler(self):
        for rec in self:
            fillert = 0
            if len(rec.picking_ids) > 0:
                for picking in rec.picking_ids:
                    for line in picking.move_ids_without_package:
                        if line.filler:
                            cantidad = line.product_uom_qty * line.filler if line.product_uom_qty > 0 else line.quantity * line.filler
                            fillert += cantidad
            rec.loaded_filler = fillert

    @api.depends('picking_ids','vehicle_weight')
    def _calculate_loaded_weight(self):
        for rec in self:
            weightt = 0
            if len(rec.picking_ids) > 0:
                for picking in rec.picking_ids:
                    for line in picking.move_ids_without_package:
                        if line.weight:
                            cantidad = line.product_uom_qty * line.weight if line.product_uom_qty > 0 else line.quantity * line.weight
                            weightt += cantidad
            rec.loaded_weight = weightt

    @api.depends('km_estimate', 'coste_km')
    def _compute_total_value_road(self):
        for rec in self:
            rec.total_value_road = rec.km_estimate * rec.coste_km
            
    @api.depends('initial_km', 'end_km')
    def _compute_km_total(self):
        for rec in self:
            rec.km_total = rec.end_km - rec.initial_km

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                company_id = vals.get('company_id', self.env.company.id)

                vals['name'] = self.env['ir.sequence'].with_company(company_id).next_by_code('dispatch.control') or '/'

        return super().create(vals_list)

    @api.ondelete(at_uninstall=False)
    def _unlink_if_not_done(self):
        if any(dispatch.state == 'done' for dispatch in self):
            raise UserError(_("No se pueden eliminar los controles de despachos realizados."))

    def action_confirm(self):
        self.ensure_one()

        if not self.picking_ids:
            raise UserError(_("Tienes que selecciona por lo menos un picking"))
        
        if self.loaded_filler > self.vehicle_filler:
            raise ValidationError(f'El cargamento excede la cantidad máxima de filler del vehículo.\nFiller del vehículo: {self.vehicle_filler:.2f}\nFiller Cargado: {self.loaded_filler:.2f}')
        else:
            pass

        if self.loaded_weight > self.vehicle_weight:
            raise ValidationError(f'El cargamento excede la capacidad máxima de peso del vehículo.\nCapacidad de Peso del vehículo: {self.vehicle_weight:.2f}\nPeso Cargado: {self.loaded_weight:.2f}')
        else:
            pass
        
        self._check_company()
        self._assined_picking()
        self.state = 'in_progress'
        return True

    def action_cancel(self):
        self.ensure_one()
        self.state = 'cancel'
        self._unassined_picking()
        self.picking_ids = False
        return True
    
    def action_draft(self):
        self.ensure_one()
        self.state = 'draft'
        return True

    def action_print(self):
        self.ensure_one()
        return self.env.ref('gchakao_custom.action_dispatch_control_report').report_action(self)

    def action_done(self):
        self.ensure_one()
        self._check_company()

        self.state = 'done'

    # -------------------------------------------------------------------------
    # Miscellaneous
    # -------------------------------------------------------------------------   

    def _assined_picking(self):
        for move in self.move_ids:
            if move.dispatch_status != 'assigned':
                move.dispatch_status = 'assigned'  

        for picking in self.picking_ids:
            if picking.dispatch_assigned == False:
                picking.dispatch_assigned = True  

    def _unassined_picking(self):
        for move in self.move_ids:
            if move.dispatch_status == 'assigned':
                move.dispatch_status = ' '   

        for picking in self.picking_ids:
            if picking.dispatch_assigned == True:
                picking.dispatch_assigned = False 
     
    def get_responsible(self):
        return self.env['res.users'].search([('id', '=', self.env.uid)]).name
    
    def get_zones(self):
        zones = []
        result = ''
        for picking in self.picking_ids:
            zones += [picking.city_id]
        z_len = len(set(zones))
        for zone in set(zones):
            if zone:
                result += zone
                if z_len > 1:
                    result += ', '
            z_len -= 1
        return result

    def get_qty_clients(self):
        clients = []
        result = ''
        for picking in self.picking_ids:
            clients += [picking.partner_id]
        result = len(set(clients))
        return result

    def get_zone_volumen(self, city_id):
        total_filler = sum(self.picking_ids.mapped('filler_total'))
        filtered_pickings = self.picking_ids.filtered(lambda p: p.city_id.id == city_id.id)
        result = sum(filtered_pickings.mapped('filler_total'))
        
        # Información de depuración
        picking_info = [(p.id, p.city_id.name, p.filler_total) for p in self.picking_ids]
        
        raise UserError(f"total_filler: {total_filler}\n"
                        f"result: {result}\n"
                        f"city_id: {city_id}\n"
                        f"Todos los pickings: {picking_info}\n")
        
        if total_filler == 0:
            return 0
        return (result / total_filler) * 100
    
    def get_qty_products(self):
        product_qty = 0
        for picking in self.picking_ids:
            for line in picking.move_ids_without_package:
                if line.quantity > 0:
                    product_qty += line.quantity
                else:
                    product_qty += line.product_uom_qty
        return product_qty



class DispatchControlRoad(models.Model):
    _name = 'dispatch.control.road'
    _description = 'Rutas de Picking Batch'

    dispatch_control_id = fields.Many2one(
        'dispatch.control',
        string='Picking Batch',
        ondelete='cascade'
    )
    road = fields.Char(
        string='Ruta'
    )
    city_id = fields.Many2one(
        'res.city',
        string='Ciudad'
    )
    kilometres = fields.Float(
        string='Kilómetros'
    )