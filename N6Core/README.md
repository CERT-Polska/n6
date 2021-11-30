**Note:** `N6Core` contains legacy *Python-2-only* stuff.  Typically,
you will want to use -- instead of it -- the new, *Python-3-only* stuff
residing in `N6DataPipeline`.

Then it comes to data sources -- i.e., collectors and parsers --
`N6DataSources` is the place where new sources should be implemented
(in Python 3).  The collectors and parsers residing in `N6Core` will
be gradually migrated to `N6DataSources` (if not obsolete).
