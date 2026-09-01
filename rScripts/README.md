# rScripts — hardware routines

These run inside a FORMS mission and reach the bench: PSU channels, the
cryocooler board, TVAC shroud heaters, the sLTA imaging chain.

They are **workspace content, not package code**. FORMS loads them by name from
`<workspace>/rScripts` (`forms.core.paths.rscripts_dir()`), so they are never
imported from `formslab` — copy or symlink this directory into your FORMS
workspace:

    ln -s "$(pwd)/rScripts" /path/to/workspace/rScripts     # POSIX
    cmd /c mklink /D  C:\path\to\workspace\rScripts  %CD%\rScripts   # Windows

Each script imports two things: `formslab.devices.*` for the instruments and
`formslab.console.cast.castutils` for the CAST request/status channel the
console reads. Both need `formslab` installed; running a mission needs the
`[forms]` extra as well.

`rTemplate` is the starting point for a new routine.
