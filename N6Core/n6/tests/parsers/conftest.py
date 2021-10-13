#  Copyright (c) 2021 NASK. All rights reserved.

# Prevent *pytest* from trying to collect tests from a file that is
# a template rather than a real module (that would cause unnecessary
# exceptions...).
collect_ignore = ["_parser_test_template.py"]
