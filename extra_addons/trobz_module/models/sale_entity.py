from odoo import fields, models, api, _

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    commercial_entity_id = fields.Many2one(
        'res.partner', string='Commercial Entity', store=True
    )