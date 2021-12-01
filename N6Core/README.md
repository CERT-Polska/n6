**Note:** `N6Core` contains legacy *Python-2-only* stuff.

When it comes to the basic *n6* pipeline components, please use the new,
*Python-3-only* stuff residing in `N6DataPipeline`.

When it comes to the data-sources-related components -- i.e., collectors
and parsers -- `N6DataSources` is the place where any new stuff is to be
implemented (in Python 3).  The collectors and parsers residing in
`N6Core` will be gradually migrated to `N6DataSources` (for those data
sources than are not obsolete).
