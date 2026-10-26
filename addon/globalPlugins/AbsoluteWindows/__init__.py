# __init__.py
# Copyright (C) 2026 Chai Chaimee
# Licensed under GNU General Public License. See COPYING.txt for details.

# This file is intentionally a thin entry point only (Section 3.1). All
# business logic, the GlobalPlugin class, dialogs, and gesture bindings live
# in addonCore.py and the other sibling modules it imports. This split also
# retires the old engine.py draft, which was never actually imported anywhere
# and had accumulated an incompatible callback signature with menu.py plus
# several references to cmd_tools functions that were never implemented;
# everything in it worth keeping has been merged into addonCore.py. Remove
# engine.py from the add-on folder - it is fully superseded and unused.

import addonHandler

addonHandler.initTranslation()

from .addonCore import GlobalPlugin
