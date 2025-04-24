from odoo import api, fields, models

class ResUsers(models.Model):
    _inherit = 'res.users'

    hide_menu_ids = fields.Many2many(
        'ir.ui.menu', 
        string="Menús Ocultos",
        help='Observe los elementos de menú que deben estar ocultos para este usuario. Modifique la <Plantilla de menú> en caso de requerirse.',
    )

    menu_template_ids = fields.Many2many(
        'hide.menu.template', 
        string="Plantillas de Menú", 
        help='Seleccione las plantillas de menú para este usuario.',
        onchange='_onchange_menu_template_ids', 
    )

    is_admin = fields.Boolean(
        compute='_compute_is_admin', 
        string="Es Administrador",
        help='Verifique si el usuario es un administrador.'
    )

    @api.depends('menu_template_ids')
    def _compute_is_admin(self):
        for rec in self:
            rec.is_admin = rec.id == self.env.ref('base.user_admin').id

    @api.onchange('menu_template_ids')
    def _onchange_menu_template_ids(self):
        pass  # No es necesario hacer nada aquí

    @api.model
    def create(self, vals):
        user = super(ResUsers, self).create(vals)
        self._update_hide_menu_ids(user)
        return user

    def write(self, vals):
        res = super(ResUsers, self).write(vals)
        if 'menu_template_ids' in vals:
            for user in self:
                self._update_hide_menu_ids(user)
        return res

    def _update_hide_menu_ids(self, user):
        user.hide_menu_ids = [(5, 0, 0)]  # Limpia los menús ocultos actuales
        for template in user.menu_template_ids:
            user.hide_menu_ids |= template.menu_ids  # Agrega los menús de la plantilla

class HideMenuTemplate(models.Model):
    _name = 'hide.menu.template'
    _description = 'Plantilla de Menú Oculto'

    name = fields.Char(required=True, string="Nombre")
    menu_ids = fields.Many2many('ir.ui.menu', string="Menús")

    @api.model
    def write(self, vals):
        res = super(HideMenuTemplate, self).write(vals)
        if res:
            # Actualizar menús ocultos para todos los usuarios que tengan esta plantilla
            for template in self:
                users = self.env['res.users'].search([('menu_template_ids', 'in', template.ids)])
                for user in users:
                    user._update_hide_menu_ids(user)
        return res

class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    restrict_user_ids = fields.Many2many(
        'res.users', 
        string="Usuarios Restringidos",
        help='Usuarios restringidos de acceder a este menú.'
    )

    @api.returns('self')
    def _filter_visible_menus(self):
        self.env['ir.ui.menu'].sudo().clear_caches()
        res = super(IrUiMenu, self)._filter_visible_menus()
        if res and self.env.user and self.env.user.hide_menu_ids:
            return res.filtered(lambda m: m.id not in self.env.user.hide_menu_ids.ids)
        return res