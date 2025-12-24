# -*- coding: utf-8 -*-
from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    sale_order_id = fields.Many2one(
        "sale.order",
        string="Sale Order",
        index=True,
        ondelete="set null",
    )

    po_type = fields.Selection(
        [
            ("manufacturing", "Manufacturing"),
            ("shipping", "Shipping"),
        ],
        string="PO Type",
        index=True,
    )
