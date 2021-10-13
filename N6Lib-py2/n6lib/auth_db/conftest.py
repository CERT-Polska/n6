#  Copyright (c) 2021 NASK. All rights reserved.

# Prevent *pytest* from trying to collect doctests from the `alembic`
# non-package subdirectory (that would cause unnecessary exceptions...).
collect_ignore = ["alembic"]
