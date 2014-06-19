# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.model import ModelView, fields
from trytond.pyson import Eval

__all__ = ['Party', 'PurchaseRequest', 'Production', 'Purchase']
__metaclass__ = PoolMeta


class Party:
    __name__ = 'party.party'
    # Should be a property
    # Should probably be external_warehouse
    external_location = fields.Many2One('stock.location', 'External Location',
        domain=[
            ('type', '=', 'storage'),
            ])

class PurchaseRequest:
    __name__ = 'purchase.request'

    @classmethod
    def origin_get(cls):
        res = super(PurchaseRequest, cls).origin_get()
        Model = Pool().get('ir.model')
        models = Model.search([
                ('model', '=', 'production'),
                ])
        for model in models:
            res.append([model.model, model.name])
        return res


class Production:
    __name__ = 'production'

    subcontract_product = fields.Many2One('product.product',
        'Subcontract Product',  domain=[('purchasable', '=', True)])
    purchase_request = fields.Many2One('purchase.request',
        'Purchase Request', readonly=True)
    outgoing_shipment = fields.Many2One('stock.shipment.internal',
        'Outgoing Shipment', readonly=True)
    incoming_shipment = fields.Many2One('stock.shipment.internal',
        'Internal Shipment', readonly=True)

    @classmethod
    def __setup__(cls):
        super(Production, cls).__setup__()
        # TODO: Do not allow starting a production if purchase_request has been
        # created but purchase order is not in processing state.
        cls._buttons.update({
                'create_purchase_request': {
                    'invisible': ~Eval('state').in_(['draft', 'waiting']),
                    'icon': 'tryton-go-home',
                    }
                })

    @classmethod
    def copy(cls, productions, default=None):
        if default is None:
            default = {}
        default['purchase_request'] = None
        default['outgoing_shipment'] = None
        default['incoming_shipment'] = None
        return super(Production, cls).copy(productions, default)

    @classmethod
    @ModelView.button
    def create_purchase_request(cls, productions):
        PurchaseRequest = Pool().get('purchase.request')
        for production in productions:
            if not production.subcontract_product:
                continue
            if not production.state in ('draft', 'waiting'):
                continue
            request, = PurchaseRequest.create([{
                        'product': production.subcontract_product.id,
                        'company': production.company.id,
                        'uom': production.subcontract_product.default_uom.id,
                        'quantity': production.quantity,
                        'computed_quantity': production.quantity,
                        'warehouse': production.warehouse.id,
                        'origin': ('production', production.id),
                        }])
            production.purchase_request = request
            production.save()

    @classmethod
    def process_purchase_request(cls, productions):
        pool = Pool()
        ShipmentInternal = pool.get('stock.shipment.internal')
        Move = pool.get('stock.move')
        for production in productions:
            # Create outgoing internal shipment
            shipment = ShipmentInternal()
            from_location = production.warehouse.storage_location
            purchase = production.purchase_request.purchase_line.purchase
            to_location = purchase.party.external_location
            shipment.from_location = from_location
            shipment.to_location = to_location
            shipment.moves = []
            for input_ in production.inputs:
                move = Move()
                move.shipment = shipment
                move.from_location = from_location
                move.to_location = to_location
                move.product = input_.product
                # TODO: Support lots
                move.quantity = input_.quantity
                move.uom = input_.uom
                shipment.moves.append(move)
            shipment.save()
            production.outgoing_shipment = shipment

            # Create incoming internal shipment

            # TODO: Production location should be taken from the destination
            # warehouse
            tmp = from_location
            from_location = to_location
            to_location = tmp
            shipment = ShipmentInternal()
            shipment.from_location = from_location
            shipment.to_location = to_location
            shipment.moves = []
            for output in production.outputs:
                move = Move()
                move.from_location = from_location
                move.to_location = to_location
                move.product = output.product
                # TODO: Support lots
                move.quantity = output.quantity
                move.uom = output.uom
                shipment.moves.append(move)
            shipment.save()
            production.incoming_shipment = shipment

            location = from_location
            # Update production
            #production.warehouse =
            for move in production.inputs:
                move.from_location = location
                move.save()

            for move in production.outputs:
                move.to_location = location
                move.save()

            production.save()


    # Missing function to synchronize output production moves with incoming
    # internal shipment. Should emulate behaviour of ShipmentOut and ShipmentIn
    # where there is no direct linke between stock moves but are calculated by
    # product and quantities. See _sync_inventory_to_outgoing in
    # stock/shipment.py.


class Purchase:
    __name__ = 'purchase.purchase'

    @classmethod
    def process(cls, purchases):
        pool = Pool()
        PurchaseRequest = pool.get('purchase.request')
        Production = pool.get('production')

        super(Purchase, cls).process(purchases)

        lines = []
        for purchase in purchases:
            for line in purchase.lines:
                lines.append(line.id)

        requests = PurchaseRequest.search([
                ('purchase_line', 'in', lines),
                ])
        requests = [x.id for x in requests]
        productions = Production.search([
                ('purchase_request', 'in', requests),
                ])
        if productions:
            Production.process_purchase_request(productions)
