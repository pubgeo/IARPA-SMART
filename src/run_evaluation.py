#!/bin/env python
# © 2024 The Johns Hopkins University Applied Physics Laboratory LLC.  This material was sponsored by the U.S. Government under contract number 2020-20081800401.
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in 
# the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of 
# the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS 
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER 
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""
The contents of this file were moved into the "iarpa_smart_metrics" module.

If the ``iarpa_smart_metrics`` metrics has been pip installed, this is callable
via:

.. code-block:: bash

    python -m iarpa_smart_metrics.run_evaluation

This script serves to maintain any backwards compatability.
"""
import sys
from iarpa_smart_metrics import run_evaluation

if __name__ == '__main__':
    try:
        run_evaluation.main()
    except Exception as ex:
        print(f"\nSTARTUP ERROR: {ex}\nExiting the program...")
        sys.exit(-1)