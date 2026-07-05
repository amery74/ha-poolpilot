# Changelog

## v1.0.0

### Stable release
- First stable release of the Pool Pilot Home Assistant integration.
- Stable startup behavior with non-blocking initialization.
- Persistent Pool House products and maintenance data.
- Persistent strip test history.
- Notification preferences saved safely.
- Compatible with Home Assistant 2026.6+.

### Features
- Smart filtration recommendations.
- Automatic filtration scheduling.
- Water chemistry monitoring.
- Pool House product inventory.
- Product recommendation engine.
- Strip test tracking.
- Persistent notifications and mobile notify services.
- Daily summary and reminder options.
- Diagnostic sensors and attributes for Lovelace cards.

### Stability
- Fixed startup blocking caused by weather, refresh, notification, or automation tasks.
- Fixed notification service coordinator lookup.
- Fixed Home Assistant 2026.6 runtime compatibility.
- Made weather forecast refresh safe when the weather entity is unavailable.

## v0.8.30
- Introduced minimal boot mode.
- Coordinator is registered before setup work begins.
- Deferred weather refresh, timers, and auto-schedule startup tasks.

## v0.8.28
- Fixed notification preference saving on Home Assistant 2026.6.
- Protected notification services from coordinator lookup errors.
