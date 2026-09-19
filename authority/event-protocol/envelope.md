# Event envelope, revision, conflict and revocation rules

This is the normative reference for the conformance corpus. `event_protocol.py`
and `eventprotocol` (Go) implement exactly this rule set.

## 1. Common envelope

Every NostrHost-controlled addressable document defines these content fields.
They are optional on legacy documents (treated as schema 1); new documents
should carry them.

| Field | Type | Meaning |
|---|---|---|
| `schema` | integer ≥ 1 | Document schema version. Absent means version 1. |
| `server` | 64-hex string | Stable server public key the document belongs to. |
| `subject` | string | Stable resource id, mirrored in the `d` tag. |
| `enabled` | boolean | Explicit active/disabled state where revocation is meaningful. |
| `revision` | integer ≥ 0 | Monotonic logical revision scoped to the address. |
| `updated_by` | string | Initiating event id when it differs from the signer. |
| `reason` | string | Optional bounded, non-secret operator explanation. |

Address and participants use standard Nostr tags (`d`, `p`, `e`). Content is
canonical JSON where hashes or fixture comparison depend on serialization.

The envelope never carries secret material. Validators reject a `secret`-shaped
value only in the kinds where a JSON Schema forbids the field; broad secret
scanning is out of scope here (see WP6).

## 2. Verbs and reason codes

Validation returns `accept` or `reject` plus a stable code. Rules are applied in
the order below; each fixture violates exactly one rule.

| Code | Meaning |
|---|---|
| `content-not-json` | Non-empty content is not valid JSON (kinds whose content is defined as JSON: `31100`, `31101`, `31102`). |
| `missing-d` | Addressable kind has no non-empty `d` tag. |
| `d-not-hex64` | `d` must be the subject pubkey (64-hex). |
| `schema-invalid` | `schema` present but not an integer ≥ 1. |
| `revision-invalid` | `revision` present but not an integer ≥ 0. |
| `subject-mismatch` | Addressable envelope declares a `subject` that differs from `d`. |
| `31100:missing-type` | Capability has no non-empty `type`. |
| `31100:scopes-not-array` | Capability `scopes` present but not an array of strings. |
| `31101:missing-schema` | Trust/policy document has no `schema`. |
| `31102:missing-username` | Enabled identity definition has no non-empty `username`. |
| `31102:bad-signer-type` | `signer_type` not one of `nip07|nip46|passkey|unknown`. |
| `31102:enabled-not-bool` | `enabled` present but not boolean. |
| `31102:admin-not-bool` | `admin` present but not boolean. |
| `27236:bad-tags` | Delegation `p`/`server` tags missing or not 64-hex. |
| `27236:bad-expiry` | Delegation `expiry` tag missing or not a positive integer. |
| `27236:missing-scope` | Delegation has no `scope` tag. |
| `27237:missing-e` | Revocation has no 64-hex `e` tag. |
| `30000:missing-d` | Permission set has no non-empty `d` tag. |
| `30000:bad-p` | Permission-set `p` tag not 64-hex. |
| `10000:bad-p` | Mute-list `p` tag not 64-hex. |
| `10002:bad-r` | Relay list `r` tag missing or not a `ws://`/`wss://` URL. |


## 3. Replacement and deterministic conflict resolution

For addressable state, an effective fact is a fold over the valid events for one
address `(kind, d)`:

1. Accept only events from an author authorized for that address (see
   `authority/authority-matrix.toml`); authorization is enforced before folding.
2. `revision(event)` = `content.revision` when present, else `0`.
3. Select the greatest `revision`.
4. On equal revision, tie-break by `(created_at, event_id)`; when two events
   share a revision but differ, emit a conflict notice.
5. A revision that does not advance the current effective revision does not
   replace it; it is superseded, not applied.
6. Timestamp skew is bounded at relay ingress, but arrival order is never
   authority.

Legacy producers that omit `revision` all fold at revision 0 and therefore
resolve by `(created_at, event_id)` — exactly the NIP-33 replaceable behavior
they have today. Adding `revision` later lets a client override the tie-break
without rewriting history.

## 4. Revocation

- Semantic revocation is `enabled: false` (identity) or an empty `scopes`
  list (capability). Revoked definitions stay stored; they are not deleted.
- NIP-09 deletion requests alone are insufficient for authorization revocation
  because replicas may retain the original event.
- Replaceable lists are revoked by a newer valid empty/changed list, not by
  physical database deletion.
- Delegation revocation (kind `27237`) is authoritative by referenced event id.

## 5. Schema-version compatibility policy

- Readers support the current and the previous schema version of a document.
- A migration publishes a new revision of the addressable document; it never
  rewrites or deletes an accepted event.
- An unknown future schema version is quarantined with a bounded reason and does
  not become effective; the last-known-good projection stays active.
- Removing a required field is a schema bump; adding an optional field is not.
- `schema` is required on new kinds (`31101` onwards); legacy kinds are read as
  version 1 until they publish a revision carrying `schema`.
