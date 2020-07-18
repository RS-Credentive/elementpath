#
# Copyright (c), 2018-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
XSD atomic datatypes. Includes a class for UntypedAtomic data and classes
for other XSD built-in primitive types. This module raises only built-in
exceptions in order to be reusable in other packages.
"""
from abc import ABC, ABCMeta, abstractmethod
import operator
import re
import codecs
import datetime
import base64
from collections import namedtuple
from calendar import isleap, leapdays
from decimal import Decimal
from urllib.parse import urlparse


###
# Data validation helpers

WHITESPACES_PATTERN = re.compile(r'\s+')
NMTOKEN_PATTERN = re.compile(r'^[\w.\-:\u00B7\u0300-\u036F\u203F\u2040]+$')
NAME_PATTERN = re.compile(r'^(?:[^\d\W]|:)[\w.\-:\u00B7\u0300-\u036F\u203F\u2040]*$')
NCNAME_PATTERN = re.compile(r'^[^\d\W][\w.\-\u00B7\u0300-\u036F\u203F\u2040]*$')
QNAME_PATTERN = re.compile(
    r'^(?:(?P<prefix>[^\d\W][\w\-.\u00B7\u0300-\u036F\u0387\u06DD\u06DE\u203F\u2040]*):)?'
    r'(?P<local>[^\d\W][\w\-.\u00B7\u0300-\u036F\u0387\u06DD\u06DE\u203F\u2040]*)$',
)
HEX_BINARY_PATTERN = re.compile(r'^[0-9a-fA-F]+$')
BASE64_BINARY_PATTERN = re.compile(
    r'((([A-Za-z0-9+/] ?){4})*(([A-Za-z0-9+/] ?){3}[A-Za-z0-9+/]|([A-Za-z0-9+/] ?){2}'
    r'[AEIMQUYcgkosw048] ?=|[A-Za-z0-9+/] ?[AQgw] ?= ?=))?'
)

LANGUAGE_CODE_PATTERN = re.compile(r'^[a-zA-Z]{1,8}(-[a-zA-Z0-9]{1,8})*$')
WRONG_ESCAPE_PATTERN = re.compile(r'%(?![a-fA-f\d]{2})')


def decimal_validator(value):
    return isinstance(value, (int, Decimal)) and not isinstance(value, bool)


def integer_validator(value):
    return isinstance(value, int) and not isinstance(value, bool)


def base64_binary_validator(value):
    if isinstance(value, bytes):
        value = value.decode()
    elif not isinstance(value, str):
        return False

    value = value.replace(' ', '')
    if not value:
        return True

    match = BASE64_BINARY_PATTERN.match(value)
    if match is None or match.group(0) != value:
        return False

    try:
        base64.standard_b64decode(value)
    except (ValueError, TypeError):
        return False
    else:
        return True


def hex_binary_validator(value):
    if isinstance(value, bytes):
        value = value.decode()
    elif not isinstance(value, str):
        return False

    value = value.strip()
    if not value:
        return True

    return not len(value) % 2 and HEX_BINARY_PATTERN.match(value) is not None


def any_uri_validator(value):
    if isinstance(value, bytes):
        value = value.decode()
    elif not isinstance(value, str):
        return False

    try:
        urlparse(value)
    except ValueError:
        return False
    else:
        return value.count('#') <= 1 and \
            WRONG_ESCAPE_PATTERN.search(value) is None


def datetime_stamp_validator(value):
    return isinstance(value, str) and DateTime.pattern.match(value) is not None


def ncname_validator(value):
    return isinstance(value, str) and NCNAME_PATTERN.match(value) is not None


def is_id(value):
    return isinstance(value, str) and ncname_validator(value)


def is_idrefs(value):
    return isinstance(value, str) and all(ncname_validator(x) for x in value.split())


###
# Date/Time helpers
MONTH_DAYS = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
MONTH_DAYS_LEAP = [0, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def adjust_day(year, month, day):
    if month in {1, 3, 5, 7, 8, 10, 12}:
        return day
    elif month in {4, 6, 9, 11}:
        return min(day, 30)
    else:
        return min(day, 29) if isleap(year) else min(day, 28)


def days_from_common_era(year):
    """
    Returns the number of days from from 0001-01-01 to the provided year. For a
    common era year the days are counted until the last day of December, for a
    BCE year the days are counted down from the end to the 1st of January.
    """
    if year > 0:
        return year * 365 + year // 4 - year // 100 + year // 400
    elif year >= -1:
        return year * 366
    else:
        year = -year - 1
        return -(366 + year * 365 + year // 4 - year // 100 + year // 400)


DAYS_IN_4Y = days_from_common_era(4)
DAYS_IN_100Y = days_from_common_era(100)
DAYS_IN_400Y = days_from_common_era(400)


def months2days(year, month, months_delta):
    """
    Converts a delta of months to a delta of days, counting from the 1st day of the month,
    relative to the year and the month passed as arguments.

    :param year: the reference start year, a negative or zero value means a BCE year \
    (0 is 1 BCE, -1 is 2 BCE, -2 is 3 BCE, etc).
    :param month: the starting month (1-12).
    :param months_delta: the number of months, if negative count backwards.
    """
    if not months_delta:
        return 0

    total_months = month - 1 + months_delta
    target_year = year + total_months // 12
    target_month = total_months % 12 + 1

    if month <= 2:
        y_days = 365 * (target_year - year) + leapdays(year, target_year)
    else:
        y_days = 365 * (target_year - year) + leapdays(year + 1, target_year + 1)

    months_days = MONTH_DAYS_LEAP if isleap(target_year) else MONTH_DAYS
    if target_month >= month:
        m_days = sum(months_days[m] for m in range(month, target_month))
        return y_days + m_days if y_days >= 0 else y_days + m_days
    else:
        m_days = sum(months_days[m] for m in range(target_month, month))
        return y_days - m_days if y_days >= 0 else y_days - m_days


class Timezone(datetime.tzinfo):
    """
    A tzinfo implementation for XSD timezone offsets. Offsets must be specified
    between -14:00 and +14:00.

    :param offset: a timedelta instance or an XSD timezone formatted string.
    """
    _maxoffset = datetime.timedelta(hours=14, minutes=0)
    _minoffset = -_maxoffset

    def __init__(self, offset):
        super(Timezone, self).__init__()
        if not isinstance(offset, datetime.timedelta):
            raise TypeError("offset must be a datetime.timedelta")
        if offset < self._minoffset or offset > self._maxoffset:
            raise ValueError("offset must be between -14:00 and +14:00")
        self.offset = offset

    @classmethod
    def fromstring(cls, text):
        try:
            hours, minutes = text.strip().split(':')
            if hours.startswith('-'):
                return cls(datetime.timedelta(hours=int(hours), minutes=-int(minutes)))
            else:
                return cls(datetime.timedelta(hours=int(hours), minutes=int(minutes)))
        except AttributeError:
            raise TypeError("argument is not a string")
        except ValueError:
            if text.strip() == 'Z':
                return cls(datetime.timedelta(0))
            raise ValueError("%r: not an XSD timezone formatted string" % text) from None

    @classmethod
    def fromduration(cls, duration):
        return cls(datetime.timedelta(seconds=int(duration.seconds)))

    def __getinitargs__(self):
        return self.offset,

    def __hash__(self):
        return hash(self.offset)

    def __eq__(self, other):
        return isinstance(other, Timezone) and self.offset == other.offset

    def __ne__(self, other):
        return not isinstance(other, Timezone) or self.offset != other.offset

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self.offset)

    def __str__(self):
        return self.tzname(None)

    def utcoffset(self, dt):
        if not isinstance(dt, datetime.datetime) and dt is not None:
            raise TypeError("utcoffset() argument must be a "
                            "datetime.datetime instance or None")
        return self.offset

    def tzname(self, dt):
        if not isinstance(dt, datetime.datetime) and dt is not None:
            raise TypeError("tzname() argument must be a "
                            "datetime.datetime instance or None")

        if not self.offset:
            return 'Z'
        elif self.offset < datetime.timedelta(0):
            sign, offset = '-', -self.offset
        else:
            sign, offset = '+', self.offset

        hours, minutes = offset.seconds // 3600, offset.seconds // 60 % 60
        return '{}{:02d}:{:02d}'.format(sign, hours, minutes)

    def dst(self, dt):
        if not isinstance(dt, datetime.datetime) and dt is not None:
            raise TypeError("dst() argument must be a "
                            "datetime.datetime instance or None")

    def fromutc(self, dt):
        if isinstance(dt, datetime.datetime):
            return dt + self.offset
        elif dt is not None:
            raise TypeError("fromutc() argument must be a "
                            "datetime.datetime instance or None")


###
# Classes for XSD built-in primitive types

class AbstractDateTime(metaclass=ABCMeta):
    """
    A class for representing XSD date/time objects. It uses and internal datetime.datetime
    attribute and an integer attribute for processing BCE years or for years after 9999 CE.
    """
    version = '1.0'
    pattern = re.compile(r'^$')
    _utc_timezone = Timezone(datetime.timedelta(0))
    _year = None

    def __init__(self, year=2000, month=1, day=1, hour=0, minute=0,
                 second=0, microsecond=0, tzinfo=None):
        if hour == 24 and minute == second == 0:
            delta = datetime.timedelta(days=1)
            hour = 0
        else:
            delta = 0

        if 1 <= year <= 9999:
            self._dt = datetime.datetime(year, month, day, hour, minute,
                                         second, microsecond, tzinfo)
        elif year == 0:
            raise ValueError('0 is an illegal value for year')
        elif not isinstance(year, int):
            raise TypeError("wrong type %r for year" % type(year))
        else:
            self._year = year
            if isleap(year + bool(self.version != '1.0')):
                self._dt = datetime.datetime(4, month, day, hour, minute,
                                             second, microsecond, tzinfo)
            else:
                self._dt = datetime.datetime(6, month, day, hour, minute,
                                             second, microsecond, tzinfo)

        if delta:
            self._dt += delta

    def __repr__(self):
        fields = self.pattern.groupindex.keys()
        arg_string = ', '.join(
            str(getattr(self, k))
            for k in ['year', 'month', 'day', 'hour', 'minute'] if k in fields
        )
        if 'second' in fields:
            if self.microsecond:
                arg_string += ', %d.%06d' % (self.second, self.microsecond)
            else:
                arg_string += ', %d' % self.second

        if self.tzinfo is not None:
            arg_string += ', tzinfo=%r' % self.tzinfo
        return '%s(%s)' % (self.__class__.__name__, arg_string)

    @abstractmethod
    def __str__(self):
        raise NotImplementedError()

    @property
    def year(self):
        return self._year or self._dt.year

    @property
    def bce(self):
        return self._year is not None and self._year < 0

    @property
    def iso_year(self):
        """The ISO string representation of the year field."""
        year = self.year
        if -9999 <= year < -1:
            return '{:05}'.format(year if self.version == '1.0' else year + 1)
        elif year == -1:
            return '-0001' if self.version == '1.0' else '0000'
        elif 0 <= year <= 9999:
            return '{:04}'.format(year)
        else:
            return str(year)

    @property
    def month(self):
        return self._dt.month

    @property
    def day(self):
        return self._dt.day

    @property
    def hour(self):
        return self._dt.hour

    @property
    def minute(self):
        return self._dt.minute

    @property
    def second(self):
        return self._dt.second

    @property
    def microsecond(self):
        return self._dt.microsecond

    @property
    def tzinfo(self):
        return self._dt.tzinfo

    @tzinfo.setter
    def tzinfo(self, tz):
        self._dt = self._dt.replace(tzinfo=tz)

    @classmethod
    def fromstring(cls, datetime_string, tzinfo=None):
        """
        Creates an XSD date/time instance from a string formatted value.

        :param datetime_string: a string containing an XSD formatted date/time specification.
        :param tzinfo: optional implicit timezone information, must be a `Timezone` instance.
        :return: an AbstractDateTime concrete subclass instance.
        """
        if not isinstance(datetime_string, str):
            msg = '1st argument has an invalid type {!r}'
            raise TypeError(msg.format(type(datetime_string)))
        elif tzinfo and not isinstance(tzinfo, Timezone):
            msg = '2nd argument has an invalid type {!r}'
            raise TypeError(msg.format(type(tzinfo)))

        match = cls.pattern.match(datetime_string.strip())
        if match is None:
            msg = 'Invalid datetime string {!r} for {!r}'
            raise ValueError(msg.format(datetime_string, cls))

        kwargs = {k: int(v) if k != 'tzinfo' else Timezone.fromstring(v)
                  for k, v in match.groupdict().items() if v is not None}

        if 'tzinfo' not in kwargs and tzinfo is not None:
            kwargs['tzinfo'] = tzinfo
        if 'microsecond' in kwargs:
            pow10 = 6 - len(match.groupdict()['microsecond'])
            kwargs['microsecond'] = 0 if pow10 < 0 else kwargs['microsecond'] * 10**pow10
        if 'year' in kwargs:
            year_digits = match.groupdict()['year'].lstrip('-')
            if year_digits.startswith('0') and len(year_digits) > 4:
                msg = "Invalid datetime string {!r} for {!r} (when year " \
                      "exceeds 4 digits leading zeroes are not allowed)"
                raise ValueError(msg.format(datetime_string, cls))

            if kwargs['year'] <= 0 and cls.version != '1.0':
                kwargs['year'] -= 1

        return cls(**kwargs)

    @classmethod
    def fromdatetime(cls, dt, year=None):
        """
        Creates an XSD date/time instance from a datetime.datetime/date/time instance.

        :param dt: the datetime, date or time instance that stores the XSD Date/Time value.
        :param year: if an year is provided the created instance refers to it and the \
        possibly present *dt.year* part is ignored.
        :return: an AbstractDateTime concrete subclass instance.
        """
        if not isinstance(dt, (datetime.datetime, datetime.date, datetime.time)):
            raise TypeError('1st argument has an invalid type %r' % type(dt))
        elif year is not None and not isinstance(year, int):
            raise TypeError('2nd argument has an invalid type %r' % type(year))

        kwargs = {k: getattr(dt, k) for k in cls.pattern.groupindex.keys() if hasattr(dt, k)}
        if year is not None:
            kwargs['year'] = year
        return cls(**kwargs)

    # Python can't compares offset-naive and offset-aware datetimes
    def _get_operands(self, other):
        if isinstance(other, (self.__class__, datetime.datetime)) or \
                isinstance(self, other.__class__):
            dt = getattr(other, '_dt', other)
            if self._dt.tzinfo is dt.tzinfo:
                return self._dt, dt
            elif self.tzinfo is None:
                return self._dt.replace(tzinfo=self._utc_timezone), dt
            elif dt.tzinfo is None:
                return self._dt, dt.replace(tzinfo=self._utc_timezone)
            else:
                return self._dt, dt
        else:
            raise TypeError("wrong type %r for operand %r" % (type(other), other))

    def __hash__(self):
        return hash((self._dt, self._year))

    def __eq__(self, other):
        try:
            return operator.eq(*self._get_operands(other)) and self.year == other.year
        except TypeError:
            return False

    def __ne__(self, other):
        try:
            return operator.ne(*self._get_operands(other)) or self.year != other.year
        except TypeError:
            return True


class OrderedDateTime(AbstractDateTime):

    @abstractmethod
    def __str__(self):
        raise NotImplementedError()

    @classmethod
    def fromdelta(cls, delta, adjust_timezone=False):
        """
        Creates an XSD dateTime/date instance from a datetime.timedelta related to
        0001-01-01T00:00:00 CE. In case of a date the time part is not counted.

        :param delta: a datetime.timedelta instance.
        :param adjust_timezone: if `True` adjusts the timezone of Date objects \
        with eventually present hours and minutes.
        """
        try:
            dt = datetime.datetime(1, 1, 1) + delta
        except OverflowError:
            days = delta.days
            if days > 0:
                y400, days = divmod(days, DAYS_IN_400Y)
                y100, days = divmod(days, DAYS_IN_100Y)
                y4, days = divmod(days, DAYS_IN_4Y)
                y1, days = divmod(days, 365)
                year = y400 * 400 + y100 * 100 + y4 * 4 + y1 + 1
                if y1 == 4 or y100 == 4:
                    year -= 1
                    days = 365

                td = datetime.timedelta(days=days, seconds=delta.seconds,
                                        microseconds=delta.microseconds)
                dt = datetime.datetime(4 if isleap(year) else 6, 1, 1) + td

            elif days >= -366:
                year = -1
                td = datetime.timedelta(days=days, seconds=delta.seconds,
                                        microseconds=delta.microseconds)
                dt = datetime.datetime(5, 1, 1) + td

            else:
                days = -days - 366
                y400, days = divmod(days, DAYS_IN_400Y)
                y100, days = divmod(days, DAYS_IN_100Y)
                y4, days = divmod(days, DAYS_IN_4Y)
                y1, days = divmod(days, 365)
                year = -y400 * 400 - y100 * 100 - y4 * 4 - y1 - 2
                if y1 == 4 or y100 == 4:
                    year += 1
                    days = 365

                td = datetime.timedelta(days=-days, seconds=delta.seconds,
                                        microseconds=delta.microseconds)
                if not td:
                    dt = datetime.datetime(4 if isleap(year + 1) else 6, 1, 1)
                    year += 1
                else:
                    dt = datetime.datetime(5 if isleap(year + 1) else 7, 1, 1) + td
        else:
            year = dt.year

        if issubclass(cls, Date10):
            if adjust_timezone and (dt.hour or dt.minute):
                assert dt.tzinfo is None
                hour, minute = dt.hour, dt.minute

                if hour < 14 or hour == 14 and minute == 0:
                    tz = Timezone(datetime.timedelta(hours=-hour, minutes=-minute))
                    dt = dt.replace(tzinfo=tz)
                else:
                    tz = Timezone(datetime.timedelta(hours=-dt.hour + 24, minutes=-minute))
                    dt = dt.replace(tzinfo=tz)
                    dt += datetime.timedelta(days=1)

            return cls(year, dt.month, dt.day, tzinfo=dt.tzinfo)
        return cls(year, dt.month, dt.day, dt.hour, dt.minute,
                   dt.second, dt.microsecond, dt.tzinfo)

    def todelta(self):
        """Returns the datetime.timedelta from 0001-01-01T00:00:00 CE."""
        if self._year is None:
            return operator.sub(*self._get_operands(datetime.datetime(1, 1, 1)))

        year, dt = self.year, self._dt
        tzinfo = None if dt.tzinfo is None else self._utc_timezone

        if year > 0:
            m_days = MONTH_DAYS_LEAP if isleap(year) else MONTH_DAYS
            days = days_from_common_era(year - 1) + sum(m_days[m] for m in range(1, dt.month))
        else:
            m_days = MONTH_DAYS_LEAP if isleap(year + 1) else MONTH_DAYS
            days = days_from_common_era(year) + sum(m_days[m] for m in range(1, dt.month))

        delta = (dt - datetime.datetime(dt.year, dt.month, day=1, tzinfo=tzinfo))
        return datetime.timedelta(days=days, seconds=delta.total_seconds())

    def _date_operator(self, op, other):
        if isinstance(other, self.__class__):
            dt1, dt2 = self._get_operands(other)
            if self._year is None and other._year is None:
                return DayTimeDuration.fromtimedelta(dt1 - dt2)
            return DayTimeDuration.fromtimedelta(self.todelta() - other.todelta())

        elif isinstance(other, datetime.timedelta):
            delta = op(self.todelta(), other)
            return type(self).fromdelta(delta, adjust_timezone=True)

        elif isinstance(other, DayTimeDuration):
            delta = op(self.todelta(), other.get_timedelta())
            if self._dt.tzinfo is None:
                return type(self).fromdelta(delta)

            value = type(self).fromdelta(delta)
            if value.tzinfo is None:
                value.tzinfo = self._utc_timezone
            return value

        elif isinstance(other, YearMonthDuration):
            month = op(self._dt.month - 1, other.months) % 12 + 1
            year = self.year + op(self._dt.month - 1, other.months) // 12
            day = adjust_day(year, month, self._dt.day)

            if year > 0:
                dt = self._dt.replace(year=year, month=month, day=day)
            elif isleap(year):
                dt = self._dt.replace(year=4, month=month, day=day)
            else:
                dt = self._dt.replace(year=6, month=month, day=day)

            kwargs = {k: getattr(dt, k) for k in self.pattern.groupindex.keys()}
            if year <= 0:
                kwargs['year'] = year
            return type(self)(**kwargs)

        else:
            raise TypeError("wrong type %r for operand %r" % (type(other), other))

    def __lt__(self, other):
        dt1, dt2 = self._get_operands(other)
        y1, y2 = self.year, other.year
        return y1 < y2 or y1 == y2 and dt1 < dt2

    def __le__(self, other):
        dt1, dt2 = self._get_operands(other)
        y1, y2 = self.year, other.year
        return y1 < y2 or y1 == y2 and dt1 <= dt2

    def __gt__(self, other):
        dt1, dt2 = self._get_operands(other)
        y1, y2 = self.year, other.year
        return y1 > y2 or y1 == y2 and dt1 > dt2

    def __ge__(self, other):
        dt1, dt2 = self._get_operands(other)
        y1, y2 = self.year, other.year
        return y1 > y2 or y1 == y2 and dt1 >= dt2

    def __add__(self, other):
        if isinstance(other, OrderedDateTime):
            raise TypeError("wrong type %r for operand %r" % (type(other), other))
        return self._date_operator(operator.add, other)

    def __sub__(self, other):
        return self._date_operator(operator.sub, other)


class DateTime10(OrderedDateTime):
    """XSD 1.0 xs:dateTime builtin type"""
    pattern = re.compile(
        r'^(?P<year>(?:-)?[0-9]*[0-9]{4})-(?P<month>[0-9]{2})-(?P<day>[0-9]{2})'
        r'(T(?P<hour>[0-9]{2}):(?P<minute>[0-9]{2}):'
        r'(?P<second>[0-9]{2})(?:\.(?P<microsecond>[0-9]+))?)'
        r'(?P<tzinfo>Z|[+-](?:(?:0[0-9]|1[0-3]):[0-5][0-9]|14:00))?$')

    def __init__(self, year, month, day, hour=0, minute=0, second=0, microsecond=0, tzinfo=None):
        super(DateTime10, self).__init__(
            year, month, day, hour, minute, second, microsecond, tzinfo
        )

    def __str__(self):
        if self.microsecond:
            return '{}-{:02}-{:02}T{:02}:{:02}:{:02}.{}{}'.format(
                self.iso_year, self.month, self.day, self.hour, self.minute, self.second,
                '{:06}'.format(self.microsecond).rstrip('0'), str(self.tzinfo or '')
            ).rstrip('0')
        return '{}-{:02}-{:02}T{:02}:{:02}:{:02}{}'.format(
            self.iso_year, self.month, self.day, self.hour,
            self.minute, self.second, str(self.tzinfo or '')
        )


class DateTime(DateTime10):
    """XSD 1.1 xs:dateTime builtin type"""
    version = '1.1'


class Date10(OrderedDateTime):
    """XSD 1.0 xs:date builtin type"""
    pattern = re.compile(r'^(?P<year>(?:-)?[0-9]*[0-9]{4})-(?P<month>[0-9]{2})-(?P<day>[0-9]{2})'
                         r'(?P<tzinfo>Z|[+-](?:(?:0[0-9]|1[0-3]):[0-5][0-9]|14:00))?$')

    def __init__(self, year, month, day, tzinfo=None):
        super(Date10, self).__init__(year, month, day, tzinfo=tzinfo)

    def __str__(self):
        return '{}-{:02}-{:02}{}'.format(
            self.iso_year, self.month, self.day, str(self.tzinfo or '')
        )


class Date(Date10):
    """XSD 1.1 xs:date builtin type"""
    version = '1.1'


class XPathGregorianDay(AbstractDateTime):
    """xs:gDay datatype for XPath expressions"""
    pattern = re.compile(r'^---(?P<day>[0-9]{2})'
                         r'(?P<tzinfo>Z|[+-](?:(?:0[0-9]|1[0-3]):[0-5][0-9]|14:00))?$')

    def __init__(self, day, tzinfo=None):
        super(XPathGregorianDay, self).__init__(day=day, tzinfo=tzinfo)

    def __str__(self):
        return '---{:02}{}'.format(self.day, str(self.tzinfo or ''))


class GregorianDay(XPathGregorianDay, OrderedDateTime):
    """XSD xs:gDay builtin type"""


class XPathGregorianMonth(AbstractDateTime):
    """xs:gMonth datatype for XPath expressions"""
    pattern = re.compile(r'^--(?P<month>[0-9]{2})'
                         r'(?P<tzinfo>Z|[+-](?:(?:0[0-9]|1[0-3]):[0-5][0-9]|14:00))?$')

    def __init__(self, month, tzinfo=None):
        super(XPathGregorianMonth, self).__init__(month=month, tzinfo=tzinfo)

    def __str__(self):
        return '--{:02}{}'.format(self.month, str(self.tzinfo or ''))


class GregorianMonth(XPathGregorianMonth, OrderedDateTime):
    """XSD xs:gMonth builtin type"""


class XPathGregorianMonthDay(AbstractDateTime):
    """xs:gMonthDay datatype for XPath expressions"""
    pattern = re.compile(r'^--(?P<month>[0-9]{2})-(?P<day>[0-9]{2})'
                         r'(?P<tzinfo>Z|[+-](?:(?:0[0-9]|1[0-3]):[0-5][0-9]|14:00))?$')

    def __init__(self, month, day, tzinfo=None):
        super(XPathGregorianMonthDay, self).__init__(month=month, day=day, tzinfo=tzinfo)

    def __str__(self):
        return '--{:02}-{:02}{}'.format(self.month, self.day, str(self.tzinfo or ''))


class GregorianMonthDay(XPathGregorianMonthDay, OrderedDateTime):
    """XSD xs:gMonthDay builtin type"""


class XPathGregorianYear(AbstractDateTime):
    """xs:gYear datatype for XPath expressions"""
    pattern = re.compile(r'^(?P<year>(?:-)?[0-9]*[0-9]{4})'
                         r'(?P<tzinfo>Z|[+-](?:(?:0[0-9]|1[0-3]):[0-5][0-9]|14:00))?$')

    def __init__(self, year, tzinfo=None):
        super(XPathGregorianYear, self).__init__(year, tzinfo=tzinfo)

    def __str__(self):
        return '{}{}'.format(self.iso_year, str(self.tzinfo or ''))


class GregorianYear10(XPathGregorianYear, OrderedDateTime):
    """XSD 1.0 xs:gYear builtin type"""


class GregorianYear(GregorianYear10):
    """XSD 1.1 xs:gYear builtin type"""
    version = '1.1'


class XPathGregorianYearMonth(AbstractDateTime):
    """xs:gYearMonth datatype for XPath expressions"""
    pattern = re.compile(r'^(?P<year>(?:-)?[0-9]*[0-9]{4})-(?P<month>[0-9]{2})'
                         r'(?P<tzinfo>Z|[+-](?:(?:0[0-9]|1[0-3]):[0-5][0-9]|14:00))?$')

    def __init__(self, year, month, tzinfo=None):
        super(XPathGregorianYearMonth, self).__init__(year, month, tzinfo=tzinfo)

    def __str__(self):
        return '{}-{:02}{}'.format(self.iso_year, self.month, str(self.tzinfo or ''))


class GregorianYearMonth10(XPathGregorianYearMonth, OrderedDateTime):
    """XSD 1.0 xs:gYearMonth builtin type"""


class GregorianYearMonth(GregorianYearMonth10):
    """XSD 1.1 xs:gYearMonth builtin type"""
    version = '1.1'


class Time(AbstractDateTime):
    """XSD xs:time builtin type"""
    pattern = re.compile(
        r'^(?P<hour>[0-9]{2}):(?P<minute>[0-9]{2}):'
        r'(?P<second>[0-9]{2})(?:\.(?P<microsecond>[0-9]+))?'
        r'(?P<tzinfo>Z|[+-](?:(?:0[0-9]|1[0-3]):[0-5][0-9]|14:00))?$')

    def __init__(self, hour=0, minute=0, second=0, microsecond=0, tzinfo=None):
        if hour == 24 and minute == second == 0:
            hour = 0
        super(Time, self).__init__(
            hour=hour, minute=minute, second=second, microsecond=microsecond, tzinfo=tzinfo
        )

    def __str__(self):
        if self.microsecond:
            return '{:02}:{:02}:{:02}.{}{}'.format(
                self.hour, self.minute, self.second,
                '{:06}'.format(self.microsecond).rstrip('0'),
                str(self.tzinfo or '')
            )
        return '{:02}:{:02}:{:02}{}'.format(
            self.hour, self.minute, self.second, str(self.tzinfo or '')
        )

    def __lt__(self, other):
        return operator.lt(*self._get_operands(other))

    def __le__(self, other):
        return operator.le(*self._get_operands(other))

    def __gt__(self, other):
        return operator.gt(*self._get_operands(other))

    def __ge__(self, other):
        return operator.ge(*self._get_operands(other))

    def __add__(self, other):
        if isinstance(other, DayTimeDuration):
            dt = self._dt + other.get_timedelta()
        elif isinstance(other, datetime.timedelta):
            dt = self._dt + other
        else:
            raise TypeError("wrong type %r for operand %r" % (type(other), other))
        return Time(dt.hour, dt.minute, dt.second, dt.microsecond, dt.tzinfo)

    def __sub__(self, other):
        if isinstance(other, self.__class__):
            delta = operator.sub(*self._get_operands(other))
            return DayTimeDuration.fromtimedelta(delta)
        elif isinstance(other, DayTimeDuration):
            dt = self._dt - other.get_timedelta()
            return Time(dt.hour, dt.minute, dt.second, dt.microsecond, dt.tzinfo)
        elif isinstance(other, datetime.timedelta):
            dt = self._dt - other
            return Time(dt.hour, dt.minute, dt.second, dt.microsecond, dt.tzinfo)
        else:
            raise TypeError("wrong type %r for operand %r" % (type(other), other))


class Duration(object):
    """
    Base class for the XSD duration types.

    :param months: an integer value that represents years and months.
    :param seconds: a Decimal instance that represents days, hours, minutes, \
    seconds and fractions of seconds.
    """
    _pattern = re.compile(
        r'^(-)?P(?=(?:[0-9]|T))(?:([0-9]+)Y)?(?:([0-9]+)M)?(?:([0-9]+)D)?'
        r'(?:T(?=[0-9])(?:([0-9]+)H)?(?:([0-9]+)M)?(?:([0-9]+(?:\.[0-9]+)?)S)?)?$'
    )

    def __init__(self, months=0, seconds=0):
        if seconds < 0 < months or months < 0 < seconds:
            raise ValueError('signs differ: (months=%d, seconds=%d)' % (months, seconds))
        self.months = months
        self.seconds = Decimal(seconds)

    def __repr__(self):
        return '{}(months={!r}, seconds={})'.format(
            self.__class__.__name__, self.months, str(self.seconds)
        )

    def __str__(self):
        m = abs(self.months)
        years, months = m // 12, m % 12
        s = self.seconds.copy_abs()
        days = int(s // 86400)
        hours = int(s // 3600 % 24)
        minutes = int(s // 60 % 60)
        seconds = s % 60

        value = '-P' if self.sign else 'P'
        if years or months or days:
            if years:
                value += '%dY' % years
            if months:
                value += '%dM' % months
            if days:
                value += '%dD' % days

        if hours or minutes or seconds:
            value += 'T'
            if hours:
                value += '%dH' % hours
            if minutes:
                value += '%dM' % minutes
            if seconds:
                value += '%sS' % seconds.normalize()

        elif value[-1] == 'P':
            value += 'T0S'
        return value

    @classmethod
    def fromstring(cls, text):
        """
        Creates a Duration instance from a formatted XSD duration string.

        :param text: an ISO 8601 representation without week fragment and an optional decimal part \
        only for seconds fragment.
        """
        if not isinstance(text, str):
            msg = 'argument has an invalid type {!r}'
            raise TypeError(msg.format(type(text)))

        match = cls._pattern.match(text.strip())
        if match is None:
            raise ValueError('%r is not an xs:duration value' % text)

        sign, years, months, days, hours, minutes, seconds = match.groups()
        seconds = Decimal(seconds or 0)
        minutes = int(minutes or 0) + int(seconds // 60)
        seconds = seconds % 60
        hours = int(hours or 0) + minutes // 60
        minutes = minutes % 60
        days = int(days or 0) + hours // 24
        hours = hours % 24
        months = int(months or 0) + 12 * int(years or 0)

        if sign is None:
            seconds = seconds + (days * 24 + hours) * 3600 + minutes * 60
        else:
            months = -months
            seconds = -seconds - (days * 24 + hours) * 3600 - minutes * 60

        if cls is DayTimeDuration:
            if months:
                raise ValueError('months must be 0 for %r' % cls.__name__)
            return cls(seconds=seconds)
        elif cls is YearMonthDuration:
            if seconds:
                raise ValueError('seconds must be 0 for %r' % cls.__name__)
            return cls(months=months)
        return cls(months=months, seconds=seconds)

    @property
    def sign(self):
        return '-' if self.months < 0 or self.seconds < 0 else ''

    def _compare_durations(self, other, op):
        """
        Ordering is defined through comparison of four datetime.datetime values.

        Ref: https://www.w3.org/TR/2012/REC-xmlschema11-2-20120405/#duration
        """
        if not isinstance(other, self.__class__):
            raise TypeError("wrong type %r for operand %r" % (type(other), other))

        m1, s1 = self.months, int(self.seconds)
        m2, s2 = other.months, int(other.seconds)
        ms1, ms2 = int((self.seconds - s1) * 1000000), int((other.seconds - s2) * 1000000)
        return all([
            op(datetime.timedelta(months2days(1696, 9, m1), s1, ms1),
               datetime.timedelta(months2days(1696, 9, m2), s2, ms2)),
            op(datetime.timedelta(months2days(1697, 2, m1), s1, ms1),
               datetime.timedelta(months2days(1697, 2, m2), s2, ms2)),
            op(datetime.timedelta(months2days(1903, 3, m1), s1, ms1),
               datetime.timedelta(months2days(1903, 3, m2), s2, ms2)),
            op(datetime.timedelta(months2days(1903, 7, m1), s1, ms1),
               datetime.timedelta(months2days(1903, 7, m2), s2, ms2)),
        ])

    def __hash__(self):
        return hash((self.months, self.seconds))

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.months == other.months and self.seconds == other.seconds
        else:
            return other == (self.months, self.seconds)

    def __ne__(self, other):
        if isinstance(other, self.__class__):
            return self.months != other.months or self.seconds != other.seconds
        else:
            return other != (self.months, self.seconds)

    def __lt__(self, other):
        return self._compare_durations(other, operator.lt)

    def __le__(self, other):
        return self == other or self._compare_durations(other, operator.le)

    def __gt__(self, other):
        return self._compare_durations(other, operator.gt)

    def __ge__(self, other):
        return self == other or self._compare_durations(other, operator.ge)


class YearMonthDuration(Duration):

    def __init__(self, months=0):
        super(YearMonthDuration, self).__init__(months, 0)

    def __repr__(self):
        return '%s(months=%r)' % (self.__class__.__name__, self.months)

    def __str__(self):
        m = abs(self.months)
        years, months = m // 12, m % 12

        if not years:
            return '-P%dM' % months if self.months < 0 else 'P%dM' % months
        elif not months:
            return '-P%dY' % years if self.months < 0 else 'P%dY' % years
        elif self.months < 0:
            return '-P%dY%dM' % (years, months)
        else:
            return 'P%dY%dM' % (years, months)

    def __add__(self, other):
        if isinstance(other, self.__class__):
            return YearMonthDuration(months=self.months + other.months)
        elif isinstance(other, (DateTime10, Date10)):
            return other + self
        raise TypeError("wrong type %r for operand %r" % (type(other), other))

    def __sub__(self, other):
        if not isinstance(other, self.__class__):
            raise TypeError("wrong type %r for operand %r" % (type(other), other))
        return YearMonthDuration(months=self.months - other.months)

    def __mul__(self, other):
        if not isinstance(other, (float, int, Decimal)):
            raise TypeError("wrong type %r for operand %r" % (type(other), other))
        return YearMonthDuration(months=int(float(self.months * other) + 0.5))

    def __truediv__(self, other):
        if isinstance(other, self.__class__):
            return self.months / other.months
        elif isinstance(other, (float, int, Decimal)):
            return YearMonthDuration(months=int(float(self.months / other) + 0.5))
        else:
            raise TypeError("wrong type %r for operand %r" % (type(other), other))


class DayTimeDuration(Duration):

    def __init__(self, seconds=0):
        super(DayTimeDuration, self).__init__(0, seconds)

    @classmethod
    def fromtimedelta(cls, td):
        return cls(seconds=Decimal(
            '{}.{:06}'.format(td.days * 86400 + td.seconds, td.microseconds)
        ))

    def get_timedelta(self):
        return datetime.timedelta(
            seconds=int(self.seconds), microseconds=int(self.seconds % 1 * 1000000)
        )

    def __repr__(self):
        return '%s(seconds=%s)' % (self.__class__.__name__, str(self.seconds))

    def __add__(self, other):
        if not isinstance(other, self.__class__):
            raise TypeError("wrong type %r for operand %r" % (type(other), other))
        return DayTimeDuration(seconds=self.seconds + other.seconds)

    def __sub__(self, other):
        if not isinstance(other, self.__class__):
            raise TypeError("wrong type %r for operand %r" % (type(other), other))
        return DayTimeDuration(seconds=self.seconds - other.seconds)

    def __mul__(self, other):
        if not isinstance(other, (float, int, Decimal)):
            raise TypeError("wrong type %r for operand %r" % (type(other), other))
        return DayTimeDuration(seconds=int(float(self.seconds * other) + 0.5))

    def __truediv__(self, other):
        if isinstance(other, self.__class__):
            return self.seconds / other.seconds
        elif isinstance(other, (float, int, Decimal)):
            return DayTimeDuration(seconds=int(float(self.seconds / other) + 0.5))
        else:
            raise TypeError("wrong type %r for operand %r" % (type(other), other))


class AbstractBinary(ABC):
    """
    Abstract class for xs:base64Binary data.

    :param value: a string or a binary data or an untyped atomic instance.
    """
    def __init__(self, value):
        if isinstance(value, (self.__class__, UntypedAtomic)):
            value = value.value
        elif isinstance(value, (AbstractBinary, UntypedAtomic)):
            value = self.encoder(value.decode())
        elif not isinstance(value, (str, bytes)):
            raise TypeError('the argument has an invalid type %r' % type(value))

        if not self.validator(value):
            raise ValueError('invalid value {!r} for {!r}'.format(value, self.__class__))

        self.value = value if isinstance(value, bytes) else value.encode('ascii')

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.value)

    def __bytes__(self):
        return self.value

    def __str__(self):
        return self.value.decode('utf-8')

    def __eq__(self, other):
        if isinstance(other, (AbstractBinary, UntypedAtomic)):
            return self.value == other.value
        return self.value == other

    @staticmethod
    @abstractmethod
    def validator(value):
        raise NotImplementedError()

    @staticmethod
    @abstractmethod
    def encoder(value):
        raise NotImplementedError()

    @abstractmethod
    def decode(self):
        raise NotImplementedError()


class Base64Binary(AbstractBinary):
    """Class for xs:base64Binary data."""

    validator = staticmethod(base64_binary_validator)

    @staticmethod
    def encoder(value):
        return codecs.encode(value, 'base64').rstrip(b'\n')

    def decode(self):
        return codecs.decode(self.value, 'base64')


class HexBinary(AbstractBinary):
    """Class for xs:hexBinary data."""

    validator = staticmethod(hex_binary_validator)

    @staticmethod
    def encoder(value):
        return codecs.encode(value, 'hex')

    def decode(self):
        return codecs.decode(self.value, 'hex')

    def __str__(self):
        return self.value.decode('utf-8').upper()

    def __eq__(self, other):
        if isinstance(other, (AbstractBinary, UntypedAtomic)):
            return self.value.lower() == other.value.lower()
        return isinstance(other, (str, bytes)) and self.value.lower() == other.lower()


class Double(float):
    """A wrapper for handle xs:double casting and type checking."""


class AnyURI(object):
    """
    Class for xs:anyURI data.

    :param value: a string or an untyped atomic instance.
    """
    def __init__(self, value):
        if isinstance(value, str):
            self.value = value
        elif isinstance(value, bytes):
            self.value = value.decode('utf-8')
        elif isinstance(value, UntypedAtomic):
            self.value = value.value
        else:
            raise TypeError('the argument has an invalid type %r' % type(value))

        if not any_uri_validator(self.value):
            raise ValueError("invalid value {!r} for an xs:anyURI".format(value))

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.value)

    def __str__(self):
        return self.value

    def __eq__(self, other):
        if isinstance(other, (AnyURI, UntypedAtomic)):
            return self.value == other.value
        return self.value == other


class QName(object):
    """
    XPath compliant QName, bound with a prefix and a namespace.

    :param value: the prefixed name or a local name.
    :param namespace: the bound namespace, must be a not empty \
    URI if a prefixed name is provided for the 1st argument.
    """
    def __init__(self, value, namespace=None):
        if not isinstance(value, str):
            raise TypeError('the 1st argument has an invalid type %r' % type(value))
        if namespace is not None and not isinstance(namespace, str):
            raise TypeError('the 2nd argument has an invalid type %r' % type(namespace))

        self.value = value.strip()
        self.namespace = namespace

        match = QNAME_PATTERN.match(self.value)
        if match is None:
            raise ValueError('invalid value {!r} for an xs:QName'.format(self.value))

        self.prefix = match.groupdict()['prefix']
        self.local_name = match.groupdict()['local']
        if not namespace and self.prefix:
            msg = '{!r}: cannot associate a non-empty prefix with no namespace'
            raise ValueError(msg.format(self))

    @property
    def extended_name(self):
        if not self.namespace:
            return self.local_name
        return '{%s}%s' % (self.namespace, self.local_name)

    def __repr__(self):
        if not self.namespace:
            return '%s(%r)' % (self.__class__.__name__, self.value)
        return '%s(%r, namespace=%r)' % (self.__class__.__name__, self.value, self.namespace)

    def __str__(self):
        return self.value

    def __eq__(self, other):
        if isinstance(other, (QName, UntypedAtomic)):
            return self.value == other.value
        return self.value == other


class UntypedAtomic(object):
    """
    Class for xs:untypedAtomic data. Provides special methods for comparing
    and converting to basic data types.

    :param value: the untyped value, usually a string.
    """
    def __init__(self, value):
        if isinstance(value, str):
            self.value = value
        elif isinstance(value, bytes):
            self.value = value.decode('utf-8')
        elif isinstance(value, bool):
            self.value = 'true' if value else 'false'
        elif isinstance(value, (UntypedAtomic, AnyURI, QName)):
            self.value = value.value
        elif isinstance(value, AbstractBinary):
            self.value = value.value.decode('utf-8')
        elif isinstance(value, (AbstractDateTime, Duration, int, float, Decimal)):
            self.value = str(value)
        else:
            raise TypeError("{!r} is not an atomic value".format(value))

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.value)

    def _get_operands(self, other, force_float=True):
        """
        Returns a couple of operands, applying a cast to the instance value based on
        the type of the *other* argument.

        :param other: The other operand, that determines the cast for the untyped instance.
        :param force_float: Force a conversion to float if *other* is an UntypedAtomic instance.
        :return: A couple of values.
        """
        if isinstance(other, UntypedAtomic):
            if force_float:
                return float(self.value), float(other.value)
            return self.value, other.value
        elif isinstance(other, bool):
            return bool(self), other
        elif isinstance(other, int):
            return float(self.value), other
        elif isinstance(other, (AbstractDateTime, Duration)):
            return type(other).fromstring(self.value), other
        else:
            return type(other)(self.value), other

    def __hash__(self):
        return hash(self.value)

    def __eq__(self, other):
        return operator.eq(*self._get_operands(other, force_float=False))

    def __ne__(self, other):
        return not operator.eq(*self._get_operands(other, force_float=False))

    def __lt__(self, other):
        return operator.lt(*self._get_operands(other))

    def __le__(self, other):
        return operator.le(*self._get_operands(other))

    def __gt__(self, other):
        return operator.gt(*self._get_operands(other))

    def __ge__(self, other):
        return operator.ge(*self._get_operands(other))

    def __add__(self, other):
        return operator.add(*self._get_operands(other))
    __radd__ = __add__

    def __sub__(self, other):
        return operator.sub(*self._get_operands(other))

    def __rsub__(self, other):
        return operator.sub(*reversed(self._get_operands(other)))

    def __mul__(self, other):
        return operator.mul(*self._get_operands(other))
    __rmul__ = __mul__

    def __truediv__(self, other):
        return operator.truediv(*self._get_operands(other))

    def __rtruediv__(self, other):
        return operator.truediv(*reversed(self._get_operands(other)))

    def __int__(self):
        return int(self.value)

    def __float__(self):
        return float(self.value)

    def __bool__(self):
        value = self.value.strip()
        if value not in {'0', '1', 'true', 'false'}:
            raise ValueError("{!r} cannot be cast to boolean".format(self.value))
        return value in ('1', 'true')

    def __abs__(self):
        return abs(Decimal(self.value))

    def __mod__(self, other):
        return operator.mod(*self._get_operands(other))

    def __str__(self):
        return self.value

    def __bytes__(self):
        return bytes(self.value, encoding='utf-8')


####
# Type proxies for multiple type-checking in XPath expressions

class TypeProxyMeta(type):
    """
    A metaclass for creating type proxy classes, that can be used for instance
    and subclass checking and for building instances of related types. A type
    proxy class has to implement three methods as concrete class/static methods.
    """
    def __instancecheck__(cls, instance):
        return cls.instance_check(instance)

    def __subclasscheck__(cls, subclass):
        return cls.subclass_check(subclass)

    def __call__(cls, *args, **kwargs):
        return cls.instance_build(*args, **kwargs)

    def instance_check(cls, instance):
        """Checks the if the argument is an instance of one of related types."""
        raise NotImplementedError

    def subclass_check(cls, subclass):
        """Checks the if the argument is a subclass of one of related types."""
        raise NotImplementedError

    def instance_build(cls, *args, **kwargs):
        """Builds an instance belonging to one of related types."""
        raise NotImplementedError


class NumericTypeProxy(metaclass=TypeProxyMeta):
    """
    A type proxy class for xs:numeric related types (xs:float, xs:decimal and
    derived types). Builds xs:float instances.
    """
    @staticmethod
    def instance_check(other):
        return isinstance(other, (int, float, Decimal)) and \
            not isinstance(other, bool)

    @staticmethod
    def subclass_check(cls):
        if issubclass(cls, bool):
            return False
        return issubclass(cls, int) or issubclass(cls, float) \
            or issubclass(cls, Decimal)

    @staticmethod
    def instance_build(x=0):
        return float(x)


class ArithmeticTypeProxy(metaclass=TypeProxyMeta):
    """
    A type proxy class for XSD types related to arithmetic operators, including
    types related to xs:numeric and datetime or duration types. Builds xs:float
    instances.
    """

    @staticmethod
    def instance_check(other):
        return isinstance(
            other, (int, float, Decimal, AbstractDateTime, Duration, UntypedAtomic)
        ) and not isinstance(other, bool)

    @staticmethod
    def subclass_check(cls):
        if issubclass(cls, bool):
            return False
        return issubclass(cls, int) or issubclass(cls, float) or \
            issubclass(cls, Decimal) or issubclass(cls, Duration) \
            or issubclass(cls, AbstractDateTime) or issubclass(cls, UntypedAtomic)

    @staticmethod
    def instance_build(x=0):
        return float(x)


####
# XSD atomic builtins validators and values

XsdBuiltin = namedtuple('XsdBuiltin', 'validator value')
"""A namedtuple-based type for describing XSD builtin types."""

XSD_BUILTIN_TYPES = {           # pragma: no cover
    'anyType': XsdBuiltin(
        lambda x: True,
        value=UntypedAtomic('1')
    ),
    'anySimpleType': XsdBuiltin(
        lambda x: isinstance(x, (str, int, float, bool, Decimal,
                                 AbstractDateTime, Duration, Timezone, UntypedAtomic)),
        value=UntypedAtomic('1')
    ),
    'anyAtomicType': XsdBuiltin(
        lambda x: False,
        value=None
    ),
    'string': XsdBuiltin(
        lambda x: isinstance(x, str),
        value='  alpha\t'
    ),
    'decimal': XsdBuiltin(
        decimal_validator,
        value=Decimal('1.0')
    ),
    'double': XsdBuiltin(
        lambda x: isinstance(x, float),
        value=1.0
    ),
    'float': XsdBuiltin(
        lambda x: isinstance(x, float),
        value=1.0
    ),
    'date': XsdBuiltin(
        lambda x: isinstance(x, Date10),
        value=Date.fromstring('2000-01-01')
    ),
    'dateTime': XsdBuiltin(
        lambda x: isinstance(x, DateTime10),
        value=DateTime.fromstring('2000-01-01T12:00:00')
    ),
    'gDay': XsdBuiltin(
        lambda x: isinstance(x, GregorianDay),
        value=GregorianDay.fromstring('---31')
    ),
    'gMonth': XsdBuiltin(
        lambda x: isinstance(x, GregorianMonth),
        value=GregorianMonth.fromstring('--12')
    ),
    'gMonthDay': XsdBuiltin(
        lambda x: isinstance(x, GregorianMonthDay),
        value=GregorianMonthDay.fromstring('--12-01')
    ),
    'gYear': XsdBuiltin(
        lambda x: isinstance(x, GregorianYear),
        value=GregorianYear.fromstring('1999')
    ),
    'gYearMonth': XsdBuiltin(
        lambda x: isinstance(x, GregorianYearMonth),
        value=GregorianYearMonth.fromstring('1999-09')
    ),
    'time': XsdBuiltin(
        lambda x: isinstance(x, Time),
        value=Time.fromstring('09:26:54')
    ),
    'duration': XsdBuiltin(
        lambda x: isinstance(x, Duration),
        value=Duration.fromstring('P1MT1S')
    ),
    'dayTimeDuration': XsdBuiltin(
        lambda x: isinstance(x, DayTimeDuration),
        value=DayTimeDuration.fromstring('P1DT1S')
    ),
    'yearMonthDuration': XsdBuiltin(
        lambda x: isinstance(x, YearMonthDuration),
        value=YearMonthDuration.fromstring('P1Y1M')
    ),
    'QName': XsdBuiltin(
        lambda x: isinstance(x, str) and QNAME_PATTERN.match(x) is not None,
        value='xs:element'
    ),
    'NOTATION': XsdBuiltin(
        lambda x: isinstance(x, str),
        value='alpha'
    ),
    'anyURI': XsdBuiltin(
        any_uri_validator,
        value='https://example.com'
    ),
    'normalizedString': XsdBuiltin(
        lambda x: isinstance(x, str) and '\t' not in x and '\r' not in x,
        value=' alpha  ',
    ),
    'token': XsdBuiltin(
        lambda x: isinstance(x, str) and WHITESPACES_PATTERN.match(x) is None,
        value='a token'
    ),
    'language': XsdBuiltin(
        lambda x: isinstance(x, str) and LANGUAGE_CODE_PATTERN.match(x) is not None,
        value='en-US'
    ),
    'Name': XsdBuiltin(
        lambda x: isinstance(x, str) and NAME_PATTERN.match(x) is not None,
        value='_a.name::'
    ),
    'NCName': XsdBuiltin(
        ncname_validator,
        value='nc-name'
    ),
    'ID': XsdBuiltin(
        ncname_validator,
        value='id1'
    ),
    'IDREF': XsdBuiltin(
        ncname_validator,
        value='id_ref1'
    ),
    'ENTITY': XsdBuiltin(
        ncname_validator,
        value='entity1'
    ),
    'NMTOKEN': XsdBuiltin(
        lambda x: isinstance(x, str) and NMTOKEN_PATTERN.match(x) is not None,
        value='a_token'
    ),
    'base64Binary': XsdBuiltin(
        base64_binary_validator,
        value=b'YWxwaGE='
    ),
    'hexBinary': XsdBuiltin(
        hex_binary_validator,
        value=b'31'
    ),
    'dateTimeStamp': XsdBuiltin(
        datetime_stamp_validator,
        value='2000-01-01T12:00:00+01:00'
    ),
    'integer': XsdBuiltin(
        integer_validator,
        value=1
    ),
    'long': XsdBuiltin(
        lambda x: integer_validator(x) and (-2**63 <= x < 2**63),
        value=1
    ),
    'int': XsdBuiltin(
        lambda x: integer_validator(x) and (-2**31 <= x < 2**31),
        value=1
    ),
    'short': XsdBuiltin(
        lambda x: integer_validator(x) and (-2**15 <= x < 2**15),
        value=1
    ),
    'byte': XsdBuiltin(
        lambda x: integer_validator(x) and (-2**7 <= x < 2**7),
        value=1
    ),
    'positiveInteger': XsdBuiltin(
        lambda x: integer_validator(x) and x > 0,
        value=1
    ),
    'negativeInteger': XsdBuiltin(
        lambda x: integer_validator(x) and x < 0,
        value=-1
    ),
    'nonPositiveInteger': XsdBuiltin(
        lambda x: integer_validator(x) and x <= 0,
        value=0
    ),
    'nonNegativeInteger': XsdBuiltin(
        lambda x: integer_validator(x) and x >= 0,
        value=0
    ),
    'unsignedLong': XsdBuiltin(
        lambda x: integer_validator(x) and (0 <= x < 2**64),
        value=1
    ),
    'unsignedInt': XsdBuiltin(
        lambda x: integer_validator(x) and (0 <= x < 2**32),
        value=1
    ),
    'unsignedShort': XsdBuiltin(
        lambda x: integer_validator(x) and (0 <= x < 2**16),
        value=1
    ),
    'unsignedByte': XsdBuiltin(
        lambda x: integer_validator(x) and (0 <= x < 2**8),
        value=1
    ),
    'boolean': XsdBuiltin(
        lambda x: isinstance(x, bool),
        value=True
    ),
}
