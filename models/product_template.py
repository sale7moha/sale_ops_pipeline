# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    manufacturing_vendor_id = fields.Many2one(
        "res.partner",
        string="Manufacturing Vendor",
        domain=[("supplier_rank", ">", 0)],
        help="Default vendor (factory) used to create Manufacturing Purchase Orders for this product.",
    )

    shipping_cost_outside_riyadh = fields.Float(
        string="Shipping Cost (Outside Riyadh) / Unit",
        help="Per-unit shipping cost to be paid to the shipping company when delivery is outside Riyadh.",
    )
