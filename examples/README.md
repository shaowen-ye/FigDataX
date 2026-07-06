# FigDataX examples

Fixtures for a quick end-to-end sanity check.

| File | What it is |
|------|-----------|
| `scatter_demo.png` | A scatter chart with a red series (`y = 2x`, x = 0…10) and gridlines |
| `scatter_demo_calib.json` | 3-point-per-axis calibration for it (the `--calibration-points` format) |
| `scatter_demo_expected.csv` | The data FigDataX extracts from it, for regression comparison |

Regenerate them with the skill venv:

```bash
.venv/bin/python examples/make_examples.py
```

Run the extractor on the demo (writes `scatter_demo_extracted.csv` + a validation PNG
next to the input):

```bash
.venv/bin/python -m scripts.figdatax extract examples/scatter_demo.png \
    --calibration-points examples/scatter_demo_calib.json \
    --color-target 0 255 255 --subpixel --validate
```

The extracted Y values should track `2·X` to within ~0.1 (well under 1% of the axis range).
