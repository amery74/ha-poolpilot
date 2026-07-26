# Release procedure

1. Update the version in all required project files.
2. Update `CHANGELOG.md`.
3. Run local syntax and JSON checks.
4. Push the changes and wait for all GitHub Actions to pass.
5. Create a full GitHub Release named `vX.Y.Z` from the matching tag.
6. Verify installation through HACS as a custom repository.
7. For first inclusion, submit `amery74/ha-poolpilot` to the correct category in `hacs/default`.

Do not store one release-notes file per version in the repository. GitHub Releases contain release-specific notes; `CHANGELOG.md` remains the single in-repository history.
