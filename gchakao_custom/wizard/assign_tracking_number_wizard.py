from odoo import api, fields, models, http, _
from odoo.exceptions import ValidationError, UserError
from datetime import date, datetime, timedelta

class AssignTrackingNumberWizard(models.TransientModel):
    _name = 'assign.tracking.number.wizard'
    _description = 'Este wizard es para facilitar la asignación de nro de seguimiento en el picking de ventas'

    @api.model
    def _default_line_ids(self):
        picking_id = self.env.context.get('picking_id')
        line_ids = self.env['stock.move.line'].sudo().search([('picking_id','=',picking_id),('product_id.product_tmpl_id.is_battery', '=', True)])
        return line_ids.ids

    picking_id = fields.Many2one(
        'stock.picking',
        default=lambda self: self.env.context.get('picking_id'),
        string='Despacho',
    )

    line_ids = fields.Many2many(
        'stock.move.line', 
        string='Lineas del picking', 
        default=_default_line_ids,
        required=True,
    )

    state = fields.Selection(related='picking_id.state')

    def action_assign_tracking_number(self):
        for record in self.line_ids:
            record.write({'tracking_number': record.tracking_number})
        return True