# -*- coding: utf-8 -*-
{
    'name': 'Sales Operations Pipeline',

    'summary': 'Operational sales pipeline (without dashboards).',

    'version': '18.0.10.1',

    'category': 'Sales',

    'author': 'Custom',

    'license': 'LGPL-3',

    'depends': [
        'sale',
        'crm',
        'purchase',
        'stock',
        'mrp',
        'mail',
        'web',
    ],

    'data': [
        'security/ir.model.access.csv',
        'data/cron.xml',
        'data/mail_activity_types.xml',
        'data/ops_stages.xml',
        'data/shipping_product.xml',
        'views/menu.xml',
        'views/ops_manufacturing_setting_views.xml',
        'views/ops_shipping_carrier_views.xml',
        'views/ops_stage_views.xml',
        'views/product_views.xml',
        'views/purchase_order_views.xml',
        'views/sale_order_action.xml',
        'views/sale_order_form.xml',
        'views/sale_order_kanban.xml',
        'views/sale_order_list.xml',
    ],

    'assets': {},

    'post_init_hook': 'post_init_hook',
    'application': True,
    'installable': True,
}
