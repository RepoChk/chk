# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _

class ProductCategory(models.Model):
    _inherit = "product.category"

    aux_id = fields.Integer()
    aux_parent_id = fields.Integer()
