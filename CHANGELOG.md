# Changelog

All notable changes to Pool Pilot are documented in this file.

The project follows semantic versioning where possible.

## [Unreleased]

### Planned

- Continue stability testing and community feedback.

## [1.2.3] - 2026-07-26

### Added

- Maintenance Mode exposed in Home Assistant and accessible from Pool Pilot Dashboard.
- Daily filtration progress, completed duration, target duration and remaining time.
- Automatic maintenance log entries and daily summaries.

### Changed

- Improved chlorine/ORP recommendation handling and dosage exposure.
- Simplified optional electrolyzer Boost configuration.
- Pool-cover control remains a dashboard-only feature and is not part of the integration.

### Fixed

- Prevented automatic filtration restarts while Maintenance Mode is active.
- Fixed missing treatment text when a recommendation existed without a separate alert.
- Improved filtration progress consistency.

## [1.2.2-beta]

### Added

- Initial Maintenance Mode implementation.
- Filtration progress sensors and maintenance journal enhancements.
- Improved alerts and daily maintenance summaries.

## [1.2.1-beta]

### Added

- Controllable automatic-filtration placement mode.
- Configurable minimum start and maximum end times.

### Fixed

- Dashboard-controlled filtration scheduling without reopening integration options.

## [1.2.0-beta.1]

### Added

- Choice between ORP and free-chlorine measurement.
- Simple and advanced electrolyzer configuration.
- Centered or bounded-window automatic filtration.
- Detailed requested, scheduled and constrained filtration attributes.

## [1.1.1]

### Fixed

- Filtration pump command became optional.
- Separate read-only pump-state entity support.
- Safer validation of controllable pump entities.

## [1.0.1]

### Fixed

- Stability and configuration corrections after the first release.

## [1.0.0]

### Added

- First stable Pool Pilot integration release.
- Water analysis, filtration recommendations, alerts, treatment advice, Pool House and maintenance log.
