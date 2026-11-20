# GDM Transformation

## Network Reduction

You can use the `reduce` command to perform network reduction on a GDM system.

```bash
Usage: gdm [OPTIONS]

 Reduce a GDM distribution system.

Options:
  -g, --gdm-file TEXT          GDM system JSON file path.  [required]
  -t, --target-file TEXT       Target GDM system JSON file path.  [required]
  -f, --force                  Force delete the target GDM system file if
                               already exists.
  -r, --reducer [three_phase]  Reducer type to apply.  [default: three_phase]
  -ts, --time-series            Include time series data in the reduced system.
  --install-completion         Install completion for the current shell.
  --show-completion            Show completion for the current shell.
  --help                       Show this message and exit.
```

Following command converts `test.json` to `test_reduced.json` including time series data.

```bash
gdm reduce -g 'test.json' -t 'test_reduced.json' -r "three_phase" -ts
```