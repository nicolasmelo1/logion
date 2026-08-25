# SPDX-License-Identifier: MIT
"""AI Catalog v1.0 codec: decode/encode JSON ↔ frozen dataclasses."""

from __future__ import annotations

from logion_indexer._json import (
    JsonObject,
    JsonValue,
    as_object,
    opt_int,
    opt_object,
    opt_str,
    opt_str_array,
    require_str,
)

from . import (
    SPEC_VERSION,
    Attestation,
    Catalog,
    CatalogEntry,
    HostInfo,
    ProvenanceLink,
    Publisher,
    TrustManifest,
    TrustSchema,
)

#: Fields the codec knows about on a catalog entry.
_ENTRY_KNOWN_KEYS = frozenset({
    "identifier",
    "type",
    "url",
    "data",
    "displayName",
    "description",
    "tags",
    "version",
    "updatedAt",
    "publisher",
    "trustManifest",
    # ARD extension fields (§4.2) — recognized but not part of the
    # base AI Catalog spec. Preserved by the codec.
    "capabilities",
    "representativeQueries",
})

#: Fields the codec knows about on the top-level catalog.
_CATALOG_KNOWN_KEYS = frozenset({"specVersion", "entries", "host"})


class AICatalogVersionUnsupported(ValueError):
    """The catalog's specVersion is not supported by this codec."""

    error_code = "ai_catalog_version_unsupported"


class AICatalogDecodeError(ValueError):
    """A catalog document failed structural validation."""


def decode_catalog(doc: JsonValue) -> Catalog:
    """Decode a JSON value into a :class:`Catalog`.

    Raises:
        AICatalogVersionUnsupported: if ``specVersion`` is not ``"1.0"``.
        AICatalogDecodeError: if required fields are missing or malformed.
    """
    obj = as_object(doc, where="ai-catalog document")

    spec_version = opt_str(obj, "specVersion")
    if spec_version is None:
        raise AICatalogDecodeError("missing required field: specVersion")
    if spec_version != SPEC_VERSION:
        raise AICatalogVersionUnsupported(
            f"unsupported specVersion: {spec_version!r} "
            f"(supported: {SPEC_VERSION})"
        )

    entries_raw = obj.get("entries")
    if not isinstance(entries_raw, list):
        raise AICatalogDecodeError("missing or invalid field: entries")

    entries = tuple(_decode_entry(e) for e in entries_raw)

    host = None
    host_raw = opt_object(obj, "host")
    if host_raw is not None:
        host = _decode_host(host_raw)

    extra = _collect_extra(obj, _CATALOG_KNOWN_KEYS)

    return Catalog(
        spec_version=spec_version,
        entries=entries,
        host=host,
        extra=extra,
    )


def encode_catalog(catalog: Catalog) -> JsonObject:
    """Encode a :class:`Catalog` back to a JSON object."""
    result: JsonObject = {
        "specVersion": catalog.spec_version,
        "entries": [_encode_entry(e) for e in catalog.entries],
    }
    if catalog.host is not None:
        result["host"] = _encode_host(catalog.host)
    for key, value in catalog.extra:
        result[key] = value
    return result


def _decode_entry(raw: JsonValue) -> CatalogEntry:
    obj = as_object(raw, where="catalog entry")

    identifier = require_str(obj, "identifier")
    entry_type = require_str(obj, "type")

    url = opt_str(obj, "url")
    data = obj.get("data")
    if url is None and data is None:
        raise AICatalogDecodeError(
            f"entry {identifier!r}: must have 'url' or 'data'"
        )
    if url is not None and data is not None:
        raise AICatalogDecodeError(
            f"entry {identifier!r}: 'url' and 'data' are mutually exclusive"
        )

    display_name = opt_str(obj, "displayName")
    description = opt_str(obj, "description")
    tags = tuple(opt_str_array(obj, "tags"))
    version = opt_str(obj, "version")
    updated_at = opt_str(obj, "updatedAt")

    publisher = None
    pub_raw = opt_object(obj, "publisher")
    if pub_raw is not None:
        publisher = _decode_publisher(pub_raw)

    trust_manifest = None
    tm_raw = opt_object(obj, "trustManifest")
    if tm_raw is not None:
        trust_manifest = _decode_trust_manifest(tm_raw)

    capabilities = tuple(opt_str_array(obj, "capabilities"))
    representative_queries = tuple(opt_str_array(obj, "representativeQueries"))

    extra = _collect_extra(obj, _ENTRY_KNOWN_KEYS)

    return CatalogEntry(
        identifier=identifier,
        type=entry_type,
        url=url,
        data=data,
        display_name=display_name,
        description=description,
        tags=tags,
        version=version,
        updated_at=updated_at,
        publisher=publisher,
        trust_manifest=trust_manifest,
        capabilities=capabilities,
        representative_queries=representative_queries,
        extra=extra,
    )


def _encode_entry(entry: CatalogEntry) -> JsonObject:
    result: JsonObject = {
        "identifier": entry.identifier,
        "type": entry.type,
    }
    if entry.url is not None:
        result["url"] = entry.url
    elif entry.data is not None:
        result["data"] = entry.data
    _encode_entry_optional(entry, result)
    for key, value in entry.extra:
        result[key] = value
    return result


def _encode_entry_optional(
    entry: CatalogEntry,
    result: JsonObject,
) -> None:
    """Add optional fields to an encoded entry."""
    if entry.display_name is not None:
        result["displayName"] = entry.display_name
    if entry.description is not None:
        result["description"] = entry.description
    if entry.tags:
        result["tags"] = list(entry.tags)
    if entry.version is not None:
        result["version"] = entry.version
    if entry.updated_at is not None:
        result["updatedAt"] = entry.updated_at
    if entry.publisher is not None:
        result["publisher"] = _encode_publisher(entry.publisher)
    if entry.trust_manifest is not None:
        result["trustManifest"] = _encode_trust_manifest(entry.trust_manifest)
    if entry.capabilities:
        result["capabilities"] = list(entry.capabilities)
    if entry.representative_queries:
        result["representativeQueries"] = list(entry.representative_queries)


def _decode_host(raw: JsonObject) -> HostInfo:
    display_name = require_str(raw, "displayName")
    identifier = opt_str(raw, "identifier")
    documentation_url = opt_str(raw, "documentationUrl")
    logo_url = opt_str(raw, "logoUrl")
    trust_manifest = None
    tm_raw = opt_object(raw, "trustManifest")
    if tm_raw is not None:
        trust_manifest = _decode_trust_manifest(tm_raw)
    return HostInfo(
        display_name=display_name,
        identifier=identifier,
        documentation_url=documentation_url,
        logo_url=logo_url,
        trust_manifest=trust_manifest,
    )


def _encode_host(host: HostInfo) -> JsonObject:
    result: JsonObject = {"displayName": host.display_name}
    if host.identifier is not None:
        result["identifier"] = host.identifier
    if host.documentation_url is not None:
        result["documentationUrl"] = host.documentation_url
    if host.logo_url is not None:
        result["logoUrl"] = host.logo_url
    if host.trust_manifest is not None:
        result["trustManifest"] = _encode_trust_manifest(host.trust_manifest)
    return result


def _decode_publisher(raw: JsonObject) -> Publisher:
    identifier = require_str(raw, "identifier")
    display_name = require_str(raw, "displayName")
    identity_type = opt_str(raw, "identityType")
    return Publisher(
        identifier=identifier,
        display_name=display_name,
        identity_type=identity_type,
    )


def _encode_publisher(pub: Publisher) -> JsonObject:
    result: JsonObject = {
        "identifier": pub.identifier,
        "displayName": pub.display_name,
    }
    if pub.identity_type is not None:
        result["identityType"] = pub.identity_type
    return result


def _decode_trust_manifest(raw: JsonObject) -> TrustManifest:
    identity = require_str(raw, "identity")
    identity_type = opt_str(raw, "identityType")

    trust_schema = None
    ts_raw = opt_object(raw, "trustSchema")
    if ts_raw is not None:
        trust_schema = _decode_trust_schema(ts_raw)

    attestations: list[Attestation] = []
    att_raw = raw.get("attestations")
    if isinstance(att_raw, list):
        for item in att_raw:
            if isinstance(item, dict):
                attestations.append(_decode_attestation(item))

    provenance: list[ProvenanceLink] = []
    prov_raw = raw.get("provenance")
    if isinstance(prov_raw, list):
        for item in prov_raw:
            if isinstance(item, dict):
                provenance.append(_decode_provenance_link(item))

    privacy_policy_url = opt_str(raw, "privacyPolicyUrl")
    terms_of_service_url = opt_str(raw, "termsOfServiceUrl")
    signature = opt_str(raw, "signature")

    return TrustManifest(
        identity=identity,
        identity_type=identity_type,
        trust_schema=trust_schema,
        attestations=tuple(attestations),
        provenance=tuple(provenance),
        privacy_policy_url=privacy_policy_url,
        terms_of_service_url=terms_of_service_url,
        signature=signature,
    )


def _encode_trust_manifest(tm: TrustManifest) -> JsonObject:
    result: JsonObject = {"identity": tm.identity}
    if tm.identity_type is not None:
        result["identityType"] = tm.identity_type
    if tm.trust_schema is not None:
        result["trustSchema"] = _encode_trust_schema(tm.trust_schema)
    if tm.attestations:
        result["attestations"] = [
            _encode_attestation(a) for a in tm.attestations
        ]
    if tm.provenance:
        result["provenance"] = [
            _encode_provenance_link(p) for p in tm.provenance
        ]
    if tm.privacy_policy_url is not None:
        result["privacyPolicyUrl"] = tm.privacy_policy_url
    if tm.terms_of_service_url is not None:
        result["termsOfServiceUrl"] = tm.terms_of_service_url
    if tm.signature is not None:
        result["signature"] = tm.signature
    return result


def _decode_trust_schema(raw: JsonObject) -> TrustSchema:
    identifier = require_str(raw, "identifier")
    version = require_str(raw, "version")
    governance_uri = opt_str(raw, "governanceUri")
    verification_methods = tuple(opt_str_array(raw, "verificationMethods"))
    return TrustSchema(
        identifier=identifier,
        version=version,
        governance_uri=governance_uri,
        verification_methods=verification_methods,
    )


def _encode_trust_schema(ts: TrustSchema) -> JsonObject:
    result: JsonObject = {
        "identifier": ts.identifier,
        "version": ts.version,
    }
    if ts.governance_uri is not None:
        result["governanceUri"] = ts.governance_uri
    if ts.verification_methods:
        result["verificationMethods"] = list(ts.verification_methods)
    return result


def _decode_attestation(raw: JsonObject) -> Attestation:
    att_type = require_str(raw, "type")
    uri = require_str(raw, "uri")
    digest = opt_str(raw, "digest")
    size_raw = opt_int(raw, "size")
    description = opt_str(raw, "description")
    return Attestation(
        type=att_type,
        uri=uri,
        digest=digest,
        size=size_raw,
        description=description,
    )


def _encode_attestation(att: Attestation) -> JsonObject:
    result: JsonObject = {"type": att.type, "uri": att.uri}
    if att.digest is not None:
        result["digest"] = att.digest
    if att.size is not None:
        result["size"] = att.size
    if att.description is not None:
        result["description"] = att.description
    return result


def _decode_provenance_link(raw: JsonObject) -> ProvenanceLink:
    relation = require_str(raw, "relation")
    source_id = require_str(raw, "sourceId")
    source_digest = opt_str(raw, "sourceDigest")
    registry_uri = opt_str(raw, "registryUri")
    statement_uri = opt_str(raw, "statementUri")
    signature_ref = opt_str(raw, "signatureRef")
    return ProvenanceLink(
        relation=relation,
        source_id=source_id,
        source_digest=source_digest,
        registry_uri=registry_uri,
        statement_uri=statement_uri,
        signature_ref=signature_ref,
    )


def _encode_provenance_link(pl: ProvenanceLink) -> JsonObject:
    result: JsonObject = {
        "relation": pl.relation,
        "sourceId": pl.source_id,
    }
    if pl.source_digest is not None:
        result["sourceDigest"] = pl.source_digest
    if pl.registry_uri is not None:
        result["registryUri"] = pl.registry_uri
    if pl.statement_uri is not None:
        result["statementUri"] = pl.statement_uri
    if pl.signature_ref is not None:
        result["signatureRef"] = pl.signature_ref
    return result


def _collect_extra(
    obj: JsonObject,
    known_keys: frozenset[str],
) -> tuple[tuple[str, JsonValue], ...]:
    """Collect unknown keys for must-ignore preservation."""
    return tuple(
        (key, obj[key]) for key in sorted(obj) if key not in known_keys
    )
