*****************
Library Reference
*****************

.. warning::

   **It is deprecated** to use *n6sdk* as a separate library.  Instead,
   please use *n6lib* and/or other sub-packages of *n6* -- which is now
   an open-source project; see: https://github.com/CERT-Polska/n6.

   Also, **beware** that this separate *n6sdk*'s documentation is **not
   updated anymore**.  Please refer to the actual documentation of *n6*
   at https://n6.readthedocs.io/.

   In the future, most probably, we will erase *n6sdk* completely as a
   separate package, incorporating its most important parts into *n6lib*
   (possibly revamping the stuff in a backwards-incompatible way).

   Other parts of *n6sdk* will just be removed.  In particular, the
   ``n6sdk_api_test`` script (together with the ``n6sdk._api_test_tool``
   module containing its implementation) will be erased -- *without*
   incorporating it into *n6lib* (however, if you find that script useful,
   please let us know -- we might re-release it as a separate tool).


Core modules
============

.. toctree::
   :glob:
   :maxdepth: 2

   lib_basic/*


Helper modules
==============

.. toctree::
   :glob:
   :maxdepth: 2

   lib_helpers/*
