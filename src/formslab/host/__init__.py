"""The sequence host: running FORMS missions against lab hardware.

Everything in this subpackage needs the optional `[forms]` extra. Unlike
`formslab.console` and `formslab.devices` -- which run standalone and reach the
library only through `formslab.bridge` -- the host exists to drive
`forms.sequence`, so it imports FORMS directly. Without the extra installed
these modules simply do not import, and the console's `ctrl` tab reports the
`run` command as unavailable rather than failing mid-launch.
"""
