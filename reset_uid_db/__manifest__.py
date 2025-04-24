# -*- coding: utf-8 -*-
{
    'name': "Reset UID Data Base",

    'summary': """
        Reset UID Data Base""",

    'description': """
        
    """,

    'author': "José Luis Vizcaya Lopez",
    'website': "https://github.com/birkot",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/13.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',

    # any module necessary for this one to work correctly
    'depends': ['base'],

    # always loaded
    'data': [

    ],
    # only loaded in demonstration mode
    'demo': [
    ],
    'post_init_hook': 'init_reset',
    'application': False
}
