# Today read recovery

The live local and HTTPS APIs return 200 (parallel external probes under 4 seconds). These probes do not prove the iPhone WebView path. Capacitor's enabled fetch patch sends GET through its WebView proxy while login POST uses native HTTP. This is a transport discrepancy, not evidence of missing task records.

Use explicit native HTTP for authenticated JSON GETs, preserving bearer authorization and HTTP error status. Bound native transport and ignore results after cancellation; never retry writes. Today subscribes to shared read-resource state instead of maintaining a separate, stale error list. Keep previously fetched data on refresh failure; failed empty sections offer independent retry. Mobile read budgets allow cold HTTPS establishment without blocking other sections. No schema or service contract changes.

## Evidence

- Local/public authenticated API probes: notifications, automations, tasks, actions, signals and connectors return 200. Eight parallel public reads completed within 3.84 seconds during this run; this does not establish the original phone failure cause.
- Web production build, 26 client tests, style/architecture and secrets checks passed.
- CUA synthetic fault test: persistent 503 on results/schedules/runs displays separate retry controls. Restoring the fixture network and clicking results/schedules retry restores both contents and removes their errors. Subsequent failed refresh preserves the previously read result and schedule rows. Synthetic fixture is not real external execution.
- Signed iOS build and overwrite install succeeded. Automatic launch was denied because the iPhone was locked; physical-device network recovery remains to be confirmed after opening the updated app.
