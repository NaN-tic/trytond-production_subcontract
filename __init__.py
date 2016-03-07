# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from .production import *

def register():
    Pool.register(
        Party,
        PurchaseRequest,
        BOM,
        Production,
        Purchase,
        module='production_subcontract', type_='model')
