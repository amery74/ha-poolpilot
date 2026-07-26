# Contributing to Pool Pilot

Thank you for helping improve Pool Pilot.

## Before opening an issue

- Search existing issues.
- Test with the latest stable version.
- Remove credentials and personal information from logs.
- Use the provided issue form.

## Development

1. Fork the repository.
2. Create a focused branch from the development branch or current default branch.
3. Keep each pull request limited to one correction or feature.
4. Preserve backward compatibility and make new hardware support optional.
5. Do not change the dashboard layout unless the change has been discussed.
6. Update `CHANGELOG.md` under an **Unreleased** section when appropriate.

## Validation

Before submitting a pull request:

- compile the Python files;
- restart Home Assistant and check the logs;
- test configuration and options flows;
- verify that optional equipment can remain unconfigured;
- ensure HACS validation and Hassfest pass.

## Pull requests

Describe the problem, the implemented solution and the tests performed. Screenshots are welcome for visible changes.
