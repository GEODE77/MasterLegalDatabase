# Download Closeout Checklist

Run this after each future source refresh, before considering the download finished.

```bash
python -m geode.pipeline.download_closeout --root .
```

The checklist confirms four things in one place:

1. No likely API keys or tokens are present in staged or changed text files.
2. No active pending or retry downloads remain in known download summaries.
3. `_CONTROL_PLANE/NEXT_DOWNLOAD_DASHBOARD.json` was updated for the closeout date.
4. The current Git branch is clean and pushed to its upstream branch.

The report can show three statuses:

- `PASS`: the item is complete.
- `WARN`: the refresh can be closed, but known future work remains visible.
- `FAIL`: the refresh should not be considered closed yet.

Known blocked future work, such as `EO-2019-007`, is reported as a warning instead of being hidden.

For automation, use JSON output:

```bash
python -m geode.pipeline.download_closeout --root . --json
```

For stricter release gates, warnings can be treated as failures:

```bash
python -m geode.pipeline.download_closeout --root . --strict
```

Boundary: this checklist does not replace legal review, source review, or pull-request review. It only closes the operational download loop.
