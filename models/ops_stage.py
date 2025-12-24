# -*- coding: utf-8 -*-
from odoo import models, fields


class OpsStage(models.Model):
    _name = "ops.stage"
    _description = "Operations Pipeline Stage"
    _order = "sequence, id"

    name = fields.Char(string="Stage Name", required=True, translate=True)
    sequence = fields.Integer(default=10)

    fold = fields.Boolean(
        string="Folded in Kanban",
        help="This stage will be folded in the kanban view.",
    )

    is_done = fields.Boolean(
        string="Is Done Stage",
        help="Orders in this stage are considered finished/delivered.",
    )

    ops_area = fields.Selection(
        [
            ("manufacturing", "Manufacturing"),
            ("shipping", "Shipping"),
            ("other", "Other"),
            ("done", "Done"),
        ],
        string="Operational Area",
        default="other",
        required=True,
    )

    color = fields.Integer(string="Color")
