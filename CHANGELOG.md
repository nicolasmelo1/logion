# CHANGELOG

<!-- version list -->

## v0.1.10 (2026-07-01)

### Bug Fixes

- **cli**: Skip auto-update when running from the npm-managed venv
  ([#126](https://github.com/nicolasmelo1/logion/pull/126),
  [`9e6c220`](https://github.com/nicolasmelo1/logion/commit/9e6c220f92f5e3a43be3e216607210fbaaad0933))

- **companion**: Drop unpinned pip install from capabilities manifest
  ([#126](https://github.com/nicolasmelo1/logion/pull/126),
  [`9e6c220`](https://github.com/nicolasmelo1/logion/commit/9e6c220f92f5e3a43be3e216607210fbaaad0933))

- **installer**: Install companion from clean containers
  ([#125](https://github.com/nicolasmelo1/logion/pull/125),
  [`b95b58c`](https://github.com/nicolasmelo1/logion/commit/b95b58c59b7ceffdfda89228e708efd625469691))

### Features

- **cli**: Add `logion courses mine` to list your own courses
  ([#127](https://github.com/nicolasmelo1/logion/pull/127),
  [`1443836`](https://github.com/nicolasmelo1/logion/commit/1443836f129eb81859834a4956e372482f2f5842))

- **cli**: Add `logion doctor` for version + install diagnostics
  ([#126](https://github.com/nicolasmelo1/logion/pull/126),
  [`9e6c220`](https://github.com/nicolasmelo1/logion/commit/9e6c220f92f5e3a43be3e216607210fbaaad0933))

- **landing**: Hero/OG ethos hook, trust signals, live version readout, wider hero; plus CLI doctor
  + npm auto-update fix ([#126](https://github.com/nicolasmelo1/logion/pull/126),
  [`9e6c220`](https://github.com/nicolasmelo1/logion/commit/9e6c220f92f5e3a43be3e216607210fbaaad0933))

- **landing**: Lead hero + OG with the ethos hook, add trust signals
  ([#126](https://github.com/nicolasmelo1/logion/pull/126),
  [`9e6c220`](https://github.com/nicolasmelo1/logion/commit/9e6c220f92f5e3a43be3e216607210fbaaad0933))

- **landing**: Live version readout + wider hero that fits above the fold
  ([#126](https://github.com/nicolasmelo1/logion/pull/126),
  [`9e6c220`](https://github.com/nicolasmelo1/logion/commit/9e6c220f92f5e3a43be3e216607210fbaaad0933))

- **scanners**: Add native-binary execution mode to trivy/osv adapters
  ([#126](https://github.com/nicolasmelo1/logion/pull/126),
  [`9e6c220`](https://github.com/nicolasmelo1/logion/commit/9e6c220f92f5e3a43be3e216607210fbaaad0933))

### Refactoring

- Address PR review feedback ([#126](https://github.com/nicolasmelo1/logion/pull/126),
  [`9e6c220`](https://github.com/nicolasmelo1/logion/commit/9e6c220f92f5e3a43be3e216607210fbaaad0933))


## v0.1.9 (2026-06-28)

### Bug Fixes

- **cli**: Copy installed skills into agent harnesses
  ([`a6dfce5`](https://github.com/nicolasmelo1/logion/commit/a6dfce5cdeeb7adebdb05fe74c584dbcea702a29))

- **installer**: Register companion with skill metadata
  ([`4ef1533`](https://github.com/nicolasmelo1/logion/commit/4ef1533830843c1efb70d268be1741f600b6abe8))


## v0.1.8 (2026-06-28)

### Bug Fixes

- **installer**: Retry cli package installs
  ([`1f7f487`](https://github.com/nicolasmelo1/logion/commit/1f7f487221e8b36d08a35445e854b94ae2583740))

### Features

- **update**: Add persisted cli auto-update policy
  ([`4a075e9`](https://github.com/nicolasmelo1/logion/commit/4a075e9c43f3c59f6dc78560e849773fa718c979))


## v0.1.7 (2026-06-28)

### Bug Fixes

- **auth**: Persist onboarding api key
  ([`c540ddf`](https://github.com/nicolasmelo1/logion/commit/c540ddfd1a1b893e3f66beaad70ccb8301b65993))


## v0.1.6 (2026-06-28)

### Bug Fixes

- **update**: Send cli headers when downloading installer
  ([`854c991`](https://github.com/nicolasmelo1/logion/commit/854c991f22818c6c66620ec9f2a593f71b8eef1e))


## v0.1.5 (2026-06-28)

### Bug Fixes

- **installer**: Clear stale pipx venv before install
  ([`31533cf`](https://github.com/nicolasmelo1/logion/commit/31533cf43f895343047c8cd9e9308cdec6877b1a))

- **onboarding**: Reuse installed companion bundle
  ([`06c2443`](https://github.com/nicolasmelo1/logion/commit/06c24435c8d9a583c8a8c4eabd15e487cf2aa957))

- **release**: Use published companion checksum
  ([`b14df14`](https://github.com/nicolasmelo1/logion/commit/b14df14ecf481abca74862113d93da80603d614e))

### Chores

- **release**: Bump cli to 0.1.5
  ([`e95fc9c`](https://github.com/nicolasmelo1/logion/commit/e95fc9c9f2345877d2341a0d52788c022ea9ac0b))


## v0.1.4 (2026-06-28)

### Bug Fixes

- **release**: Allow manifest checks with committed assets
  ([`5e6b2e5`](https://github.com/nicolasmelo1/logion/commit/5e6b2e5d779ce81e89f2e78d09c57028f9766d65))

- **update**: Add full logion updater
  ([`1758b4c`](https://github.com/nicolasmelo1/logion/commit/1758b4c326883d8dfd88067d161e478507a59dc2))


## v0.1.3 (2026-06-28)

### Bug Fixes

- **installer**: Resolve companion release tag
  ([`495d500`](https://github.com/nicolasmelo1/logion/commit/495d500480b4ff0e534c2f07a932418dd0d99146))


## v0.1.2 (2026-06-28)

### Bug Fixes

- **release**: Prepare 0.1.2 npm managed wrapper
  ([#124](https://github.com/nicolasmelo1/logion/pull/124),
  [`9b92f33`](https://github.com/nicolasmelo1/logion/commit/9b92f33917db0e500875f2add45690f81ce51ae4))


## v0.1.1 (2026-06-28)

### Bug Fixes

- Repair npm release workflow ([#123](https://github.com/nicolasmelo1/logion/pull/123),
  [`2f9ae65`](https://github.com/nicolasmelo1/logion/commit/2f9ae6532aae1f8c6f5c83c718d0811669ad952e))

- Repair npm release workflow ([#122](https://github.com/nicolasmelo1/logion/pull/122),
  [`67f4cb3`](https://github.com/nicolasmelo1/logion/commit/67f4cb3cfbf1365e48b66de103fadcdcd04e2832))

- **release**: Prepare 0.1.1 logion-only cli
  ([#123](https://github.com/nicolasmelo1/logion/pull/123),
  [`2f9ae65`](https://github.com/nicolasmelo1/logion/commit/2f9ae6532aae1f8c6f5c83c718d0811669ad952e))


## v0.1.0 (2026-06-28)

- Initial Release
