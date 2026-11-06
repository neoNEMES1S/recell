# Simscape source handoff (unexecuted)

The numeric exporter is tested in Python. MATLAB/Simscape are unavailable locally;
the `.m` and `.ssc` sources have **not been compiled or executed**. This is not a
completed Simscape validation. The code targets R2025a+ with MATLAB, Simulink and
Simscape (Foundation electrical library); no Simscape Battery toolbox is assumed.
Verify licensed products and source compatibility on the actual installation.

Export a reviewed measured case using `scripts/export_simscape_case.py`, then in
MATLAB add this directory to the path and call:

```matlab
run_validation("/absolute/exported/case", "/absolute/fresh/output")
```

The builder generates a local 1-RC cell, controlled current load, solver, reference
and voltage sensor. Discharge is positive. The cell's through-current branch runs
from n to p; the external load must draw that current from p to n. The validation
assertion checks the direction as well as numerical equivalence. It fails rather
than auto-changing current sign. Parameters and the initial stationary polarization
come from the exported RPT-1 fit; only the measured initial voltage anchors the
later test. It models constant OCV during a short pulse, not a full OCV/SOC law.

Current is left-held, with the instantaneous ohmic drop evaluated at each sample.
`run_validation` requests the source clock and checks two maximum solver steps.
No interpolation across discontinuities is used to hide a missing sample. Inspect
numerical error and measured residuals separately. An execution record is written
only after comparisons pass. Record source/data hashes with any returned result;
the Python handoff completion explicitly says `matlab_executed: false`.

References checked against official documentation:
[Simscape branches](https://www.mathworks.com/help/simscape/lang/branches.html),
[programmatic connections, R2025a+](https://www.mathworks.com/help/simscape/ref/simscape.addconnection.html),
[controlled-current source ports](https://www.mathworks.com/help/simscape/ref/controlledcurrentsource.html),
[signal conversion](https://www.mathworks.com/help/simscape/ref/simulinkpsconverter.html).
