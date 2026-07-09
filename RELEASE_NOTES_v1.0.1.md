# Pool Pilot v1.0.1

Maintenance release focused on small fixes reported after the v1.0.0 release.

## Fixed

- Filtering mode now consistently uses Home Assistant-facing values: `off`, `manual`, and `auto`.
- Legacy `auto_intelligent` values are normalized to `auto`.
- The filtering mode selector should no longer display `unknown`.
- The duplicated `auto_schedule_detail` attribute was removed. Use `detail` instead.
- Version metadata was updated for v1.0.1.
