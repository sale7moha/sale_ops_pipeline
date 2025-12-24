# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# =========================================================
# Riyadh city normalization
# =========================================================
RYADH_NAMES = {
    "riyadh", "alriyadh", "al riyadh",
    "الرياض", "لرياض"
}


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # =========================================================
    # Operational Pipeline
    # =========================================================
    ops_stage_id = fields.Many2one(
        "ops.stage",
        string="مرحلة العمليات",
        tracking=True,
        index=True,
        group_expand="_group_expand_ops_stage_id",
    )

    @api.model
    def _group_expand_ops_stage_id(self, stages, domain, order=None):
        return self.env["ops.stage"].search([], order="sequence asc")

    # =========================================================
    # Kanban Helper Fields (Stored)
    # =========================================================
    kanban_products_summary = fields.Text(
        string="ملخص المنتجات (كانبان)",
        compute="_compute_kanban_products_summary",
        store=True,
    )

    kanban_city = fields.Char(
        string="المدينة (كانبان)",
        compute="_compute_kanban_city",
        store=True,
    )

    kanban_delivery_date = fields.Date(
        string="تاريخ التوصيل المتوقع",
        compute="_compute_kanban_delivery_date",
        store=True,
    )

    delivery_state = fields.Selection(
        [
            ("late", "متأخر"),
            ("today", "اليوم"),
            ("future", "مستقبلي"),
        ],
        string="حالة التوصيل",
        compute="_compute_delivery_state",
        store=True,
    )

    # =========================================================
    # Shipping Configuration
    # =========================================================
    shipping_type = fields.Selection(
        [
            ("riyadh", "داخل الرياض"),
            ("outside", "خارج الرياض"),
        ],
        string="نوع الشحن",
        compute="_compute_shipping_type",
        store=True,
        readonly=True,
    )

    # من ينفذ الشحن؟
    # - company: سائق الشركة (لا ننشئ PO للشحن)
    # - carrier: شركة شحن (ننشيء PO حسب القواعد)
    shipping_execution = fields.Selection(
        [
            ("company", "سائق الشركة"),
            ("carrier", "شركة شحن"),
        ],
        string="تنفيذ الشحن",
        default="carrier",
        required=True,
    )

    # اختيار شركة الشحن من الإعدادات الجديدة (ops.shipping.carrier)
    shipping_carrier_id = fields.Many2one(
        "ops.shipping.carrier",
        string="شركة الشحن",
        help="عند اختيار شركة شحن سيتم استخدام مدد الشحن منها وكذلك إنشاء PO عند الحاجة.",
    )

    # الحقول القديمة (Fallback) لتفادي كسر أي بيانات قديمة
    shipping_vendor_id = fields.Many2one(
        "res.partner",
        string="مورد الشحن",
        domain=[("supplier_rank", ">", 0)],
        help="يستخدم فقط إذا كان تنفيذ الشحن = شركة شحن (في حال لم تستخدم شركة الشحن من الإعدادات).",
    )

    shipping_service_product_id = fields.Many2one(
        "product.product",
        string="منتج خدمة الشحن",
        domain=[("type", "=", "service")],
        help="منتج خدمة يُستخدم كسطر واحد في PO الشحن لكل طلب.",
    )

    # =========================================================
    # PO Counters (for stat buttons)
    # =========================================================
    manufacturing_po_count = fields.Integer(
        string="طلبات شراء التصنيع",
        compute="_compute_po_counts",
        store=False,
    )

    shipping_po_count = fields.Integer(
        string="طلبات شراء الشحن",
        compute="_compute_po_counts",
        store=False,
    )

    # =========================================================
    # Kanban Computations
    # =========================================================
    @api.depends(
        "order_line.product_id",
        "order_line.product_uom_qty",
        "order_line.display_type",
    )
    def _compute_kanban_products_summary(self):
        for order in self:
            lines = []
            for line in order.order_line:
                if line.display_type or not line.product_id:
                    continue
                qty = line.product_uom_qty or 0.0
                lines.append(f"{line.product_id.display_name} × {qty:g}")
            order.kanban_products_summary = "\n".join(lines) if lines else False

    @api.depends("partner_shipping_id.city")
    def _compute_kanban_city(self):
        for order in self:
            order.kanban_city = order.partner_shipping_id.city if order.partner_shipping_id else False

    # =========================================================
    # Helpers: Order categories
    # =========================================================
    def _ops_get_order_categories(self):
        self.ensure_one()
        return self.order_line.filtered(
            lambda l: (not l.display_type) and l.product_id and l.product_id.categ_id
        ).mapped("product_id.categ_id")

    # =========================================================
    # Helpers: Manufacturing days from config (CORRECT MODEL/FIELD)
    # =========================================================
    def _ops_get_mfg_days_from_config(self):
        """
        يجلب مدة التصنيع من شاشة:
          ops.manufacturing.setting
        والحقل:
          manufacturing_days
        المنطق: نأخذ أقصى مدة بين فئات المنتجات الموجودة في الطلب.
        """
        self.ensure_one()
        cats = self._ops_get_order_categories()
        if not cats:
            return 0

        # ✅ الموديل الصحيح داخل الموديول
        if "ops.manufacturing.setting" not in self.env:
            return 0

        Config = self.env["ops.manufacturing.setting"].sudo()
        rows = Config.search([
            ("active", "=", True),
            ("product_category_id", "in", cats.ids),
        ])
        if not rows:
            return 0

        days = [int(r.manufacturing_days or 0) for r in rows]
        return max(days) if days else 0

    # =========================================================
    # Helpers: Shipping days
    # =========================================================
    def _ops_get_shipping_days(self):
        """
        - إذا تنفيذ الشحن = سائق الشركة -> 0 يوم
        - إذا شركة شحن:
            - إذا تم اختيار شركة شحن: نقرأ المدد منها
            - وإلا fallback: داخل=3 خارج=3
        """
        self.ensure_one()

        if self.shipping_execution == "company":
            return 0

        # إذا شركة الشحن نفسها معرفة كـ internal driver
        if self.shipping_carrier_id and self.shipping_carrier_id.is_internal:
            return 0

        if self.shipping_carrier_id:
            if self.shipping_type == "riyadh":
                return int(self.shipping_carrier_id.ship_days_riyadh or 0)
            return int(self.shipping_carrier_id.ship_days_outside or 0)

        # fallback
        return 3 if self.shipping_type == "riyadh" else 3

    # =========================================================
    # Expected Delivery Date (Manufacturing + Shipping)
    # =========================================================
    @api.depends(
        "date_order",
        "order_line.product_id",
        "order_line.product_uom_qty",
        "order_line.display_type",
        "order_line.product_id.categ_id",
        "shipping_type",
        "shipping_execution",
        "shipping_carrier_id",
        "shipping_carrier_id.ship_days_riyadh",
        "shipping_carrier_id.ship_days_outside",
    )
    def _compute_kanban_delivery_date(self):
        """
        ✅ تاريخ البداية: من تاريخ الطلب (date_order) وليس تاريخ اليوم
        ✅ التصنيع: من ops.manufacturing.setting حسب فئة المنتج
        ✅ الشحن: من شركة الشحن أو 0 إذا سائق الشركة
        """
        for order in self:
            # تاريخ الطلب مع مراعاة timezone للمستخدم
            if order.date_order:
                base_dt = fields.Datetime.context_timestamp(order, order.date_order)
                base_date = base_dt.date()
            else:
                base_date = fields.Date.context_today(order)

            try:
                mfg_days = int(order._ops_get_mfg_days_from_config() or 0)
            except Exception:
                _logger.exception("Failed to compute manufacturing days for SO %s", order.name)
                mfg_days = 0

            try:
                ship_days = int(order._ops_get_shipping_days() or 0)
            except Exception:
                _logger.exception("Failed to compute shipping days for SO %s", order.name)
                ship_days = 0

            order.kanban_delivery_date = base_date + timedelta(days=(mfg_days + ship_days))

    # =========================================================
    # Delivery Status (Late / Today / Future)
    # =========================================================
    @api.depends("kanban_delivery_date")
    def _compute_delivery_state(self):
        today = fields.Date.context_today(self)
        for order in self:
            if not order.kanban_delivery_date:
                order.delivery_state = False
            elif order.kanban_delivery_date < today:
                order.delivery_state = "late"
            elif order.kanban_delivery_date == today:
                order.delivery_state = "today"
            else:
                order.delivery_state = "future"

    # =========================================================
    # Shipping Type Compute
    # =========================================================
    @api.depends("partner_shipping_id.city")
    def _compute_shipping_type(self):
        for order in self:
            city_name = order.partner_shipping_id.city if order.partner_shipping_id else False
            order.shipping_type = "riyadh" if self._is_riyadh_city(city_name) else "outside"

    @api.model
    def _is_riyadh_city(self, city_name):
        if not city_name:
            return False
        city = city_name.strip().lower()
        return (city in RYADH_NAMES) or ("riyadh" in city) or ("الرياض" in city)

    # =========================================================
    # Internal helpers: safe PO domains (avoid crashes if fields missing)
    # =========================================================
    def _ops_po_domains(self):
        self.ensure_one()
        PurchaseOrder = self.env["purchase.order"].sudo()

        has_sale_order_id = "sale_order_id" in PurchaseOrder._fields
        has_po_type = "po_type" in PurchaseOrder._fields

        if has_sale_order_id and has_po_type:
            mfg_domain = [("sale_order_id", "=", self.id), ("po_type", "=", "manufacturing")]
            ship_domain = [("sale_order_id", "=", self.id), ("po_type", "=", "shipping")]
        elif has_sale_order_id and not has_po_type:
            mfg_domain = [("sale_order_id", "=", self.id)]
            ship_domain = [("sale_order_id", "=", self.id)]
        else:
            mfg_domain = [("origin", "=", self.name)]
            ship_domain = [("origin", "=", self.name)]
        return mfg_domain, ship_domain

    # =========================================================
    # Compute PO Counters (SAFE)
    # =========================================================
    @api.depends("name")
    def _compute_po_counts(self):
        PurchaseOrder = self.env["purchase.order"].sudo()
        for order in self:
            order.manufacturing_po_count = 0
            order.shipping_po_count = 0
            if not order.id:
                continue
            try:
                mfg_domain, ship_domain = order._ops_po_domains()
                order.manufacturing_po_count = PurchaseOrder.search_count(mfg_domain)
                order.shipping_po_count = PurchaseOrder.search_count(ship_domain)
            except Exception:
                _logger.exception("Failed computing PO counters for SO %s", order.name)
                order.manufacturing_po_count = 0
                order.shipping_po_count = 0

    # =========================================================
    # Stat Button Actions (SAFE)
    # =========================================================
    def action_view_manufacturing_pos(self):
        self.ensure_one()
        try:
            mfg_domain, _ship_domain = self._ops_po_domains()
        except Exception:
            _logger.exception("Failed building domain for Manufacturing POs SO %s", self.name)
            mfg_domain = [("origin", "=", self.name)]

        return {
            "type": "ir.actions.act_window",
            "name": _("Manufacturing Purchase Orders"),
            "res_model": "purchase.order",
            "view_mode": "list,form",
            "domain": mfg_domain,
            "context": {"search_default_filter_my": 0},
        }

    def action_view_shipping_pos(self):
        self.ensure_one()
        try:
            _mfg_domain, ship_domain = self._ops_po_domains()
        except Exception:
            _logger.exception("Failed building domain for Shipping POs SO %s", self.name)
            ship_domain = [("origin", "=", self.name)]

        return {
            "type": "ir.actions.act_window",
            "name": _("Shipping Purchase Orders"),
            "res_model": "purchase.order",
            "view_mode": "list,form",
            "domain": ship_domain,
            "context": {"search_default_filter_my": 0},
        }

    # =========================================================
    # Shipping PO Creation
    # =========================================================
    def _ops_get_product_shipping_cost_outside(self, product):
        if not product:
            return 0.0
        tmpl = product.product_tmpl_id
        if not tmpl:
            return 0.0
        return float(getattr(tmpl, "shipping_cost_outside_riyadh", 0.0) or 0.0)

    def _ops_get_flat_shipping_cost_riyadh(self):
        return float(
            self.env["ir.config_parameter"].sudo().get_param(
                "sale_ops_pipeline_v3.shipping_cost_riyadh", 0.0
            ) or 0.0
        )

    def _ops_get_shipping_vendor_and_service(self):
        """
        يحدد المورد + منتج الخدمة:
        - إذا shipping_carrier_id موجودة: نأخذ vendor_id + service_product_id منها
        - وإلا نستخدم الحقول القديمة على أمر البيع
        """
        self.ensure_one()

        if self.shipping_carrier_id:
            return self.shipping_carrier_id.vendor_id, self.shipping_carrier_id.service_product_id

        return self.shipping_vendor_id, self.shipping_service_product_id

    def action_create_shipping_po(self):
        """
        Create ONE Shipping PO per Sale Order based on rules:

        - If shipping_execution = company -> NO PO
        - If shipping_execution = carrier:
            - Inside Riyadh: 1 PO line qty=1 price = flat shipping (from carrier or config)
            - Outside Riyadh: 1 PO line qty=1 price = sum(qty * product shipping cost)
        """
        PurchaseOrder = self.env["purchase.order"].sudo()
        POL = self.env["purchase.order.line"].sudo()

        has_sale_order_id = "sale_order_id" in PurchaseOrder._fields
        has_po_type = "po_type" in PurchaseOrder._fields

        for order in self:
            # سائق الشركة أو شركة شحن داخلية -> لا PO
            if order.shipping_execution != "carrier":
                continue
            if order.shipping_carrier_id and order.shipping_carrier_id.is_internal:
                continue

            vendor, service_product = order._ops_get_shipping_vendor_and_service()

            if not vendor:
                raise UserError(_("الرجاء اختيار مورد الشحن (شركة الشحن)."))
            if not service_product:
                raise UserError(_("الرجاء اختيار منتج خدمة الشحن."))

            # Prevent duplicates
            if has_sale_order_id and has_po_type:
                existing = PurchaseOrder.search_count([
                    ("sale_order_id", "=", order.id),
                    ("po_type", "=", "shipping"),
                ])
            elif has_sale_order_id:
                existing = PurchaseOrder.search_count([("sale_order_id", "=", order.id)])
            else:
                existing = PurchaseOrder.search_count([
                    ("origin", "=", order.name),
                    ("partner_id", "=", vendor.id),
                ])

            if existing:
                continue

            # Compute total shipping cost (ONE LINE)
            total_cost = 0.0

            if order.shipping_type == "riyadh":
                if order.shipping_carrier_id and order.shipping_carrier_id.cost_riyadh_flat:
                    total_cost = float(order.shipping_carrier_id.cost_riyadh_flat or 0.0)
                else:
                    total_cost = order._ops_get_flat_shipping_cost_riyadh()
            else:
                for line in order.order_line:
                    if line.display_type or not line.product_id:
                        continue
                    per_unit = order._ops_get_product_shipping_cost_outside(line.product_id)
                    if per_unit <= 0:
                        continue
                    total_cost += per_unit * (line.product_uom_qty or 0.0)

            if total_cost <= 0:
                continue

            po_vals = {
                "partner_id": vendor.id,
                "origin": order.name,
                "company_id": order.company_id.id,
            }
            if has_sale_order_id:
                po_vals["sale_order_id"] = order.id
            if has_po_type:
                po_vals["po_type"] = "shipping"

            po = PurchaseOrder.create(po_vals)

            POL.create({
                "order_id": po.id,
                "product_id": service_product.id,
                "name": _("تكلفة شحن للطلب %s (%s)") % (
                    order.name,
                    _("خارج الرياض") if order.shipping_type == "outside" else _("داخل الرياض"),
                ),
                "product_qty": 1.0,
                "product_uom": (service_product.uom_po_id.id or service_product.uom_id.id),
                "price_unit": total_cost,
                "date_planned": fields.Datetime.now(),
            })

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        for order in self:
            try:
                order.action_create_shipping_po()
            except Exception:
                _logger.exception("Failed to create Shipping PO for SO %s", order.name)
        return res

    # =========================================================
    # =========================================================
    activity_delay_days = fields.Integer(
        string="Delay (Days)",
        compute="_compute_activity_delay_days",
        store=False,
    )

    @api.depends("activity_date_deadline", "activity_state")
    def _compute_activity_delay_days(self):
        today = fields.Date.context_today(self)
        for order in self:
            if order.activity_state == "overdue" and order.activity_date_deadline:
                order.activity_delay_days = (today - order.activity_date_deadline).days
            else:
                order.activity_delay_days = 0

