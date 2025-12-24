# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class OpsShippingCarrier(models.Model):
    _name = "ops.shipping.carrier"
    _description = "شركة الشحن - إعدادات العمليات"
    _order = "sequence, id"

    active = fields.Boolean(default=True)

    name = fields.Char(string="اسم شركة الشحن", required=True, translate=True)
    sequence = fields.Integer(string="الترتيب", default=10)

    # هل الشحن داخلي (سائق الشركة)؟ إذا نعم -> لا يتم إنشاء PO شحن
    is_internal = fields.Boolean(
        string="توصيل داخلي (سائق الشركة)",
        help="إذا تم تفعيل هذا الخيار فهذا يعني أن التوصيل يتم بواسطة سائق الشركة، ولن يتم إنشاء طلب شراء (PO) للشحن."
    )

    # المورد (Vendor) المستخدم لإنشاء PO الشحن عند is_internal = False
    vendor_id = fields.Many2one(
        "res.partner",
        string="مورد شركة الشحن",
        domain=[("supplier_rank", ">", 0)],
        help="يستخدم عند إنشاء PO الشحن (فقط إذا لم يكن التوصيل داخلي)."
    )

    # منتج خدمة الشحن (Service product) الذي يوضع في سطر الـ PO
    service_product_id = fields.Many2one(
        "product.product",
        string="منتج خدمة الشحن",
        domain=[("type", "=", "service")],
        help="منتج خدمة يمثل بند الشحن داخل PO الشحن."
    )

    # =========================================
    # التكاليف
    # =========================================
    cost_riyadh_flat = fields.Float(
        string="تكلفة شحن داخل الرياض (مبلغ ثابت للطلب)",
        help="تطبق عند كون الشحن داخل الرياض، وتُسجل كسطر واحد للطلب كامل."
    )

    # خارج الرياض: التكلفة تُحسب من كرت المنتج (لكل منتج × الكمية) -> لكن PO سطر واحد بالإجمالي
    # لا نضع رقم هنا لأن مصدرها المنتجات نفسها (shipping_cost_outside_riyadh على product.template)
    note_outside = fields.Text(
        string="ملاحظة خارج الرياض",
        default="خارج الرياض: يتم احتساب تكلفة الشحن من كرت المنتج (تكلفة الوحدة × الكمية) ويتم جمعها كسطر واحد في PO."
    )

    # =========================================
    # المدد الزمنية
    # =========================================
    ship_days_riyadh = fields.Integer(string="مدة الشحن داخل الرياض (أيام)", default=1)
    ship_days_outside = fields.Integer(string="مدة الشحن خارج الرياض (أيام)", default=3)

    # =========================================
    # حقول مساعدة للواجهة
    # =========================================
    display_vendor_required = fields.Boolean(
        compute="_compute_display_vendor_required",
        string="إظهار حقول المورد",
        store=False,
    )

    @api.depends("is_internal")
    def _compute_display_vendor_required(self):
        for rec in self:
            rec.display_vendor_required = not bool(rec.is_internal)
