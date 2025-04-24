# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, tools, _
from collections import defaultdict
import re
from unidecode import unidecode
from odoo.exceptions import UserError
import logging
import random

# Configurar el logger
_logger = logging.getLogger(__name__)

class Product(models.Model):
    _inherit = "product.product"

    filler = fields.Float(related='product_tmpl_id.filler')
    brand_id = fields.Many2one(related='product_tmpl_id.brand_id')
    measure = fields.Char(related='product_tmpl_id.measure')
    model = fields.Char(related='product_tmpl_id.model')
    tarps = fields.Char(related='product_tmpl_id.tarps')
    load_speed = fields.Char(related='product_tmpl_id.load_speed')
    rin = fields.Float(related='product_tmpl_id.rin')
    tier = fields.Selection(related='product_tmpl_id.tier')
    type_tire = fields.Char(related='product_tmpl_id.type_tire')
    construction_type = fields.Selection(related='product_tmpl_id.construction_type')
    tire_class = fields.Char(related='product_tmpl_id.tire_class')
    qty_hq = fields.Char(related='product_tmpl_id.qty_hq')
    is_battery = fields.Boolean(related='product_tmpl_id.is_battery')

class ProductBrand(models.Model):
    _name = "product.brand"
    _description = "Product Brand"

    image = fields.Binary(string='Imagen')
    name = fields.Char(string='Marca')
    ranking = fields.Integer(string='Ranking')

    def update_brand_ranking(self):
        # Obtener las líneas de factura de clientes confirmadas
        invoice_lines = self.env['account.move.line'].sudo().search([
            ('move_id.move_type', '=', 'out_invoice'),
            ('move_id.state', '=', 'posted'),
            ('product_id.product_tmpl_id.brand_id', '!=', False)
        ])
        
        brand_totals = {}
        for line in invoice_lines:
            brand_id = line.product_id.product_tmpl_id.brand_id.id
            if brand_id not in brand_totals:
                brand_totals[brand_id] = 0
            brand_totals[brand_id] += line.price_subtotal
        
        brand_sales = [{'product_id.product_tmpl_id.brand_id': (brand_id, ''), 'price_subtotal': total} 
                       for brand_id, total in brand_totals.items()]
        
        # Crear un defaultdict para almacenar las ventas por marca
        sales_dict = defaultdict(float)
        
        for brand_data in brand_sales:
            brand_id = brand_data['product_id.product_tmpl_id.brand_id'][0]
            total_sales = brand_data['price_subtotal']
            sales_dict[brand_id] = total_sales

        # Obtener todos los registros de ranking
        ranking_records = self.search([])

        # Ordenar los registros por total de ventas y asignar el ranking
        sorted_rankings = sorted(ranking_records, key=lambda r: sales_dict[r.id], reverse=True)

        # Actualizar los rankings en lotes
        for rank, record in enumerate(sorted_rankings, start=1):
            record.ranking = rank

        # Confirmar los cambios en la base de datos
        self.env.cr.commit()
    

class ProductCategory(models.Model):
    _inherit = "product.category"

    type_category = fields.Selection(
        string='Tipo de Categoría', 
        selection=[
            ('V', 'Vehículo'), 
            ('N', 'Neumático'), 
            ('B', 'Baterías'), 
            ('L', 'Litros'), 
            ('A', 'Activos'), 
            ('C', 'Costos'), 
            ('G', 'Gastos'), 
            ('SV', 'Servicios'), 
            ('S', 'Suspensión'), 
            ('O', 'Otros')
        ]
    )

    is_sequence = fields.Boolean('Es secuencia',)
    short_name = fields.Char(string='Nombre corto', help='Este nombre se usara en el prefijo de la secuencia', size=7, compute='_compute_short_name', store=True, readonly=False)
    # code_sequence = fields.Char(string='Código de secuencia', readonly=True)
    category_seq_id = fields.Many2one(
        'ir.sequence', 
        string='Secuencia',
        copy=False,
        tracking=True,
    )
    category_seq_number_next = fields.Char(compute='_compute_next_seq')

    @api.depends('category_seq_id')
    def _compute_next_seq(self):
        for rec in self:
            rec.category_seq_number_next= f'{rec.category_seq_id.prefix}{str(rec.category_seq_id.number_next_actual).zfill(rec.category_seq_id.padding)}'

    def create_seq_if_not_exist(self):
        for rec in self:
            if rec.is_sequence:
                company_id = self.env.company
                name_seq = f'category.company_{company_id.id}_{rec.short_name.lower()}'
                IrSequence = self.env['ir.sequence'].with_company(company_id)

                seq = IrSequence.search([('code', '=', name_seq)], limit=1)
                if not seq:
                    seq = IrSequence.sudo().create({
                        'prefix': f'{rec.short_name}',
                        'name': f'Category sequence - ({rec.name})',
                        'code': name_seq,
                        'implementation': 'no_gap',
                        'padding': 5,
                        'number_increment': 1,
                        'company_id': company_id.id, 
                    })
                
                rec.category_seq_id = seq.id
                # rec.code_sequence = name_seq

    @api.depends('name', 'parent_id', 'is_sequence')
    def _compute_short_name(self):
        connectors = {'del', 'cual', 'por', 'y', 'o', 'a', 'en', 'de', 'la', 'el', 'los', 'las', 'para', 'con'}

        def clean_word(word):
            return re.sub(r'[^a-zA-Z0-9]', '', word)

        existing_short_names = self.search([]).mapped('short_name')  # Obtener nombres cortos existentes

        for rec in self:
            name_short = rec.name or ''
            if not rec.name:
                continue

            if not rec.short_name and rec.is_sequence and rec.name:
                words = rec.name.split()
                filtered_words = [clean_word(word) for word in words if word and word.lower() not in connectors]
                filtered_words = [word for word in filtered_words if word]

                if rec.parent_id:
                    parent_category = rec.parent_id
                    parent_words = parent_category.name.split()
                    filtered_parent_words = [clean_word(word) for word in parent_words if word and word.lower() not in connectors]
                    filtered_parent_words = [word for word in filtered_parent_words if word]
                    filtered_child_words = [clean_word(word) for word in words if word and word.lower() not in connectors]
                    filtered_child_words = [word for word in filtered_child_words if word]
                    if parent_category.name == rec.name:
                        if len(filtered_parent_words) == 1:
                            if len(filtered_parent_words[0]) > 3:
                                mid_index = len(filtered_parent_words[0]) // 2
                                name_short = (
                                    filtered_parent_words[0][:2] + 
                                    filtered_parent_words[0][mid_index-1:mid_index+1] + 
                                    filtered_parent_words[0][-2:]
                                )
                            elif len(filtered_parent_words[0]) <= 3:
                                name_short = filtered_parent_words[0] + (filtered_child_words[0][:2] if filtered_child_words else '')
                            else:
                                name_short = filtered_parent_words[0][:3] + (filtered_child_words[0][:3] if filtered_child_words else '')
                        else:
                            name_short = filtered_parent_words[0][:3] + (filtered_parent_words[1][0] if len(filtered_parent_words) > 1 else '')
                            name_short += ''.join(word[0] for word in filtered_child_words) + (filtered_child_words[-1][-1] if filtered_child_words else '')
                    else:
                        if len(filtered_parent_words) == 1 and len(filtered_child_words) == 1:
                            name_short = filtered_parent_words[0][:3] + filtered_child_words[0][:2] + filtered_child_words[0][-1]
                        elif len(filtered_parent_words) == 1 and len(filtered_child_words) > 1:
                            name_short = filtered_parent_words[0][:3] + filtered_child_words[0][:2] + filtered_child_words[1][:2]
                        elif len(filtered_parent_words) == 2 and len(filtered_child_words) == 2:
                            name_short = filtered_parent_words[0][:3] + filtered_parent_words[1][:2] + ''.join(word[0] for word in filtered_child_words)
                        elif len(filtered_parent_words) == 2 and len(filtered_child_words) == 1:
                            name_short = filtered_parent_words[0][:2] + filtered_parent_words[1][:2] + filtered_child_words[0][:3]
                        else:
                            name_short = ''.join(word[0] for word in filtered_parent_words) + ''.join(word[0] for word in filtered_child_words)
                else:
                    if len(filtered_words) == 1:                  
                        if len(filtered_words[0]) <= 6:
                            name_short = filtered_words[0]
                        elif 6 < len(filtered_words[0]) < 10:
                            name_short = filtered_words[0][:3] + filtered_words[0][-2:]
                        else:                      
                            name_short = filtered_words[0][:3] + filtered_words[0][-3:]
                    elif len(filtered_words) == 2:                  
                        name_short = filtered_words[0][:3] + filtered_words[1][:3]
                        if len(filtered_words[0]) <= 3:
                            name_short = filtered_words[0] + filtered_words[1][:3]
                    else:                  
                        name_short = ''.join(word[:2] for word in filtered_words)          

                name_short = name_short[:7]          
                name_short = unidecode(name_short)
                name_short = name_short.upper()
                print(f"Nombre corto generado para {rec.name}: {name_short}")

                if name_short not in existing_short_names:
                    rec.short_name = name_short
                    existing_short_names.append(name_short)
                else:
                    original_short_name = name_short
                    while name_short in existing_short_names:
                        last_char = name_short[-1]
                        new_char = random.choice([char for char in original_short_name if char != last_char])
                        name_short = name_short[:-1] + new_char
                    
                    rec.short_name = name_short
                    existing_short_names.append(name_short)
            else:
                rec.short_name = rec.short_name if rec.is_sequence else False 

    def create_all_seqs(self):
        categories = self.search([])
        for category in categories:
            category.create_seq_if_not_exist()

    @api.constrains('short_name')
    def _check_unique_short_name(self):
        for rec in self:
            if rec.is_sequence and rec.short_name:
                duplicate = self.search_count([
                    ('short_name', '=', rec.short_name),
                    ('id', '!=', rec.id),
                    ('is_sequence', '=', True)
                ])
                if duplicate > 0:
                    raise UserError(f"El nombre corto '{rec.short_name}' ya existe para otra categoría.")

    @api.onchange('is_sequence')
    def _onchange_is_sequence(self):
        for rec in self:
            if not rec.is_sequence:
                rec.short_name = False
                # rec.code_sequence = False

    # _sql_constraints = [
    #     ('unique_short_name', 'UNIQUE(short_name)', 'El nombre corto debe ser único.')
    # ]

