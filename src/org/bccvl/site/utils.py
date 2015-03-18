import json
from decimal import Decimal


class DecimalJSONEncoder(json.JSONEncoder):

    def default(self, o):
        """ converts Decimal to something the json module can serialize.
        Usually with python 2.7 float rounding this creates nice representations
        of numbers, but there might be cases where rounding may cause problems.
        E.g. if precision required is higher than default float rounding.
        """
        if isinstance(o, Decimal):
            return float(o)
        return super(DecimalJSONEncoder, self).default(o)

