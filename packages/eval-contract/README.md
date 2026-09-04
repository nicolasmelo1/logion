# logion-eval-contract

The portable unit another runner can execute and reproduce: the only
parser, validator, canonicalizer, and result normalizer for Logion eval
contracts and results.

- Contract media type: `application/vnd.aktp.eval-contract.v1+json`.
  Authoring YAML is normalized to this JSON *before* hashing, so the
  digest of a YAML file and of its JSON normalization are identical.
- Result media type: `application/vnd.aktp.eval-result.v1+json`.
- Extension fields live only under `extensions`; an arbitrary top-level
  key fails validation.
- Canonicalization is JCS (RFC 8785 subset); digests are SHA-256 over
  the canonical bytes.

The private backend imports a pinned released version of this package
and must not reimplement parsing or canonicalization.