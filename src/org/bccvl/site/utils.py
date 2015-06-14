from decimal import Decimal
import json
import re


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


class Period(object):
    """
    Parse DCMI period strings and provide values as attributes.

    Format set period values as valid DCMI period.

    FIXME: currently uses date strings as is and does not try to interpret them.
           the same for formatting. date's have to be given as properly formatted strings.
    """

    start = end = scheme = name = None

    def __init__(self, str):
        '''
        TODO: assumes str is unicode
        '''
        sm = re.search(r'start=(.*?);', str)
        if sm:
            self.start = sm.group(1)
        sm = re.search(r'scheme=(.*?);', str)
        if sm:
            self.scheme = sm.group(1)
        sm = re.search(r'end=(.*?);', str)
        if sm:
            self.end = sm.group(1)
        sm = re.search(r'name=(.*?);', str)
        if sm:
            self.name = sm.group(1)

    def __unicode__(self):
        parts = []
        if self.start:
            parts.append("start=%s;" % self.start)
        if self.end:
            parts.append("end=%s;" % self.end)
        if self.name:
            parts.append("name=%s;" % self.name)
        if self.scheme:
            parts.append("scheme=%s;" % self.scheme)
        return u' '.join(parts)
