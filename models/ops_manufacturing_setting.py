# -*- coding: utf-8 -*-
from odoo import models, fields


class OpsManufacturingSetting(models.Model):
    _name = "ops.manufacturing.setting"
    _description = "إعدادات مدة التصنيع حسب فئة المنتج"
    _order = "product_category_id"

    active = fields.Boolean(
        string="نشط",
        default=True
    )

    product_category_id = fields.Many2one(
        "product.category",
        string="فئة المنتج",
        required=True,
        ondelete="cascade"
    )

    manufacturing_days = fields.Integer(
        string="مدة التصنيع (بالأيام)",
        required=True,
        default=1
    )

    note = fields.Text(
        string="ملاحظات"
    )

    _sql_constraints = [
        (
            "unique_category",
            "unique(product_category_id)",
            "لا يمكن تكرار إعداد التصنيع لنفس فئة المنتج."
        )
    ]
