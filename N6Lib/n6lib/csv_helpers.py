import csv

from cStringIO import StringIO
from typing import Sequence

from n6lib.typing_helpers import String


def split_csv_row(row, delimiter=',', quotechar='"', **kwargs):
    # type: (String, ...) -> Sequence[String]
    [csv_row] = csv.reader(StringIO(row), delimiter=delimiter, quotechar=quotechar, **kwargs)
    return csv_row
