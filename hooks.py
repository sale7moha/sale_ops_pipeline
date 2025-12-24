# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID

def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    orders = env["sale.order"].search([])
    if orders:
        orders._compute_kanban_city()
        orders._compute_kanban_products_summary()
        orders._compute_kanban_delivery_date()