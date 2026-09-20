# Nsites: curated lists exploration

Status: **product and protocol exploration; not yet implemented**.

This note explores user-authored collections of nsites that are signed by the
curator and published to ordinary external Nostr relays. It builds on the
existing NIP-5A gateway, discovery and owner-signing work. It does not make a
curated item trusted, installed, mirrored, or safe merely because someone put
it in a list.

Protocol references checked 2026-09-20: [NIP-51](https://github.com/nostr-protocol/nips/blob/master/51.md)
and [NIP-5A](https://github.com/nostr-protocol/nips/blob/master/5A.md). Both are
currently draft/optional and must be pinned for an implementation release.

## Product shape

A collection is an editorial object, separate from every site it contains:

```text
curator's signer
      │
      ├── signs a NIP-51 curation set
      └── publishes the same event to selected external relays
                                      │
reader opens naddr / collection URL ──┤
                                      ├── fetch list event
                                      ├── resolve referenced NIP-5A manifests
                                      └── open sites through an nsite gateway
```

Useful first collections include “small independent blogs”, “local community
sites”, “starter templates”, “Nostr tools”, and “sites from this event”. A
collection card should show its curator, title, description, cover image,
number of entries, last update and relay availability. It should never imply
that NostrHost or the relay endorses the entries.

The Catalogue Browse surface can gain a **Collections** filter alongside Apps
and Nsites. A site card gets **Add to collection**. A collection detail view
supports ordered entries, **Open**, **Copy this site**, and **Pin this version**.
The authoring flow is deliberately small:

1. choose a title, short identifier, description and optional image;
2. add discovered or registered nsites and order them;
3. decide whether each entry follows the live site or pins a snapshot;
4. review the exact event and destination relays;
5. sign with the user's NIP-07/NIP-46 signer and publish;
6. show accepted, rejected and timed-out relays separately, then offer a share
   link.

## Wire profile

### Recommendation for an initial interoperable experiment

Use a NIP-51 curation set, kind `30004`, with the normal `d`, `title`,
`description`, and optional `image` tags. Add `t = nsite` so nsite-aware clients
can distinguish the profile without interpreting the targets first.

This is an **extension profile**, not a claim that NIP-51 currently standardises
nsite entries. NIP-51 describes kind `30004` as curation sets and says lists can
contain references to anything, but its current expected entries are kind-1
notes and kind-30023 articles. External relays can store the event and
nsite-aware clients can interoperate; generic curation clients may ignore or
mis-render the nsite references. Before calling the format generally
interoperable, propose the profile upstream in NIP-51/NIP-5A or obtain a
dedicated set kind from the NIP registry.

Do not use kind `30001`: its former special-purpose list forms are deprecated
by the current NIP-51. Do not use kind `30267` for general nsite collections:
that kind curates software-application descriptors, and many nsites have no
app descriptor. Kind `30267` remains correct for a collection that explicitly
curates apps rather than sites.

### Live versus pinned entries

- A live root site is an `a` tag with coordinate `15128:<pubkey>:`.
- A live named site is an `a` tag with coordinate
  `35128:<pubkey>:<d>`.
- An immutable version is an `e` tag pointing to a kind-`5128` snapshot event.
- The third tag value is an external relay hint for finding the referenced
  manifest. It is a hint, not authority.
- Tag order is display order. New items append by default, following NIP-51.
- Duplicate coordinates/event ids are rejected in the authoring UI.

Example:

```json
{
  "kind": 30004,
  "content": "",
  "tags": [
    ["d", "indie-web"],
    ["title", "Small independent sites"],
    ["description", "Personal sites and experiments worth wandering through."],
    ["image", "https://cdn.example/indie-web-cover.webp"],
    ["t", "nsite"],
    ["a", "15128:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:", "wss://relay.example"],
    ["a", "35128:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb:blog", "wss://relay.example"],
    ["e", "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc", "wss://relay.example"]
  ]
}
```

The list author signs this event. The site authors continue to sign their own
NIP-5A manifests. A curator cannot mutate a site, and a site owner cannot
silently mutate a pinned snapshot. A live reference intentionally follows the
newest valid replaceable/addressable manifest at that coordinate.

Per-item reviews, rankings and arbitrary metadata should not be squeezed into
extra tag positions in the first version. They have no portable NIP-51 meaning.
Ordering plus the collection description is enough for the initial product;
editorial notes can later use separately signed events if a standard profile
emerges.

### Public, private and “unlisted”

The first release should author **public collections only**. In NIP-51 public
entries are event tags. Private entries are NIP-44-encrypted into `content`
using the author's own key, which is useful for personal sync but does not
create a collection that another person can open. “Unlisted” is only a UI
label: an event published to a public relay is public and discoverable.

## Relay sharing and resolution

The share identity is the collection coordinate, encoded as an NIP-19 `naddr`
with two or three relay hints:

```text
30004:<curator-pubkey>:indie-web
```

NostrHost may also expose a human route such as
`/collections/<naddr>`, but the `naddr` is portable and the HTTP URL is only a
viewer. Copying the share link must not make the local control relay, Admin
origin, or a loopback address into a hint.

Relay selection should reuse the existing nsite publishing model:

- initialise from the user's NIP-65 kind-`10002` write relays, then the
  operator's public curation defaults;
- let the curator review and edit a bounded set (proposed maximum: six);
- sign once in the browser and broadcast the identical event to each selected
  external relay;
- succeed when at least one relay accepts, but report partial publication as
  degraded rather than fully replicated;
- retain per-relay acceptance, rejection and timeout results and offer retry
  without requesting a new signature when the event is unchanged;
- never fall back to the private control relay or an operator/catalogue key.

A reader resolves the list from the `naddr` hints first, then its configured
public curation relays. It chooses the newest valid event for the exact
`kind + pubkey + d` coordinate, breaking equal timestamps by event id as the
nsite resolver already does. It then resolves each entry from its relay hint,
the reader's nsite lookup relays, and bounded fallback relays. The collection
event is useful even when some entries are temporarily unavailable, so the UI
should render partial results with explicit unavailable states.

Discovery can query kind `30004` plus `#t = nsite` on trusted public relays.
On-demand reads should use the same limits as `nsite.discover`: bounded relay
count, event count, timeouts, response fields and no writes. Curator follows or
reputation may influence ranking, but must not become an authorization or
installation decision.

## NostrHost operation shape

Use the existing typed plan/sign/publish pattern rather than a parallel list
publisher:

| Operation | Effect | Scope | Approval |
|---|---|---|---|
| `nsite.collection.discover` | bounded external-relay read | `nsites.read` | none |
| `nsite.collection.get` | resolve one coordinate and its entries | `nsites.read` | none |
| `nsite.collection.publish.plan` | validate entries and build unsigned event + digest | `nsites.read` | none |
| `nsite.collection.publish` | validate signed event and broadcast | `nsites.publish` | confirmation |

`publish.plan` should bind the curator pubkey, `d`, ordered entry tags,
metadata and exact destination relay set. Any edit invalidates the plan. The
server validates the returned event id, signature, author, kind, coordinate,
tag bounds and digest before broadcast. It never receives the curator's
private key.

Suggested initial bounds are 100 entries, a 64-character `d`, a 120-character
title, a 500-character description, one HTTPS image URL, six publication
relays and three relay hints in a share `naddr`. The implementation should
share relay URL normalisation, SSRF filtering, signature checks, tie-breaking,
redaction and per-relay result models with nsite publishing/discovery.

Local state is a cache and convenience index only. The signed list event on
external relays is authoritative. Editing replaces the full addressable event;
deleting locally does not delete remote copies. A tombstone/delete design is a
separate protocol decision and should not be implied by a Remove button.

## Trust and safety boundaries

- A collection is a curator's opinion, not a NostrHost trust grant or package
  approval.
- Validate the list signature and every resolved manifest independently.
- Treat titles, descriptions, images, relay hints and site HTML as untrusted.
  Never render collection text as HTML.
- Fetch cover images through the normal browser privacy posture or a bounded,
  SSRF-safe proxy; do not fetch arbitrary URLs from the control plane.
- Apply the operator's NIP-51 mute list to discovery without rewriting the
  signed collection. Show that entries were hidden locally.
- A relay accepting an event proves storage, not endorsement or availability.
- Opening a site preserves the existing gateway origin isolation. Collection
  pages stay on Admin/Portal; site content stays on the dedicated nsite origin.

## Decisions before implementation

1. Confirm kind `30004` as the experimental profile and open an upstream
   NIP-51/NIP-5A discussion, or wait for a dedicated assigned set kind.
2. Decide whether Collections live only in Admin Catalogue Browse initially or
   also in the non-admin Portal “My site” surface.
3. Confirm the bounds above and whether collection cover images are direct or
   proxied.
4. Decide whether v1 includes only publishing/editing one's own lists, or also
   “save a copy” under a new curator identity.

The smallest useful milestone is read-only: resolve one shared `naddr`, render
its ordered live/snapshot entries, and prove external-relay fallback and
partial-failure behaviour. Authoring can then reuse the already proven nsite
plan, signer and per-relay publication flow.
