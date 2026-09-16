# Operator key rotation runbook

**Context.** The node's four `operator.toml` secret keys — `server_sk`,
`operator_sk`, `publisher_sk`, `notifier_sk` — were exposed in a privileged
transcript and must be treated as compromised. The portal notice key
(`notice_sk`, `portal.toml`) was **not** exposed and can be kept.

**What changes.** The control-plane admin identity (the operator pubkey)
becomes a new key. Anything the old operator signed must be re-issued:

- the operator identity link (kind-31102) for the `nostrhost` account;
- **every** kind-31100 capability grant (agent + admin) — the old grants are
  signed by the old operator and become orphaned;
- Dynette/no-hosts DNS claims — **none exist on this node today**
  (`nostrhost dns subscriptions` is empty), so nothing to re-sign.

**What is unaffected.** Login via the user signer key
`8c2e626b13dda704fb41f96ef29aac226058f8bd4429afe7420ccfe091f78371` (linked to
`nostrhost`) and the opencode MCP client key `3e524b68…` — those are separate
identities; only the *grants* signed by the old operator need re-issuing.

Current operator pubkey (old): `55cd92158f17c2eaa3d96d799d52f6a2c66878ca1fee6071630bfbe6ead553ac`

---

## 0. Pre-flight

```sh
mkdir -p /root/keys-backup-$(date +%s)/
cp -a /etc/nostrhost/operator.toml /etc/nostrhost/keys.recovery \
      /etc/nostrhost/relay.toml /etc/nostrhost/notify.toml \
      /etc/nostrhost/catalogue.env /root/keys-backup-$(date +%s)/
```

Capture the current capability grants (they must be re-issued verbatim):

```sh
/opt/nostrhost/venv/bin/python - <<'PY'
import re
from pathlib import Path
from yunohost.nostr_operations import list_capabilities
txt = Path("/etc/nostrhost/operator.toml").read_text()
op_sk = re.search(r'operator_sk\s*=\s*"([0-9a-f]{64})"', txt).group(1)
relay = re.search(r'control_relay\s*=\s*"([^"]+)"', txt).group(1)
for g in list_capabilities(admin_sk=op_sk, control_relay=relay):
    print(g.get("subject") or g.get("pubkey"), g.get("type"), " ".join(sorted(g.get("scopes", []))))
PY
```

Confirm there is nothing to re-sign for DNS:

```sh
nostrhost dns subscriptions
```

Current grant inventory (captured 2026-09-16):

| subject pubkey | type | scopes |
|---|---|---|
| `3e524b68ace3781786e0031ed35ca8e38baa4e5ecb1598114ae32dd30561d975` | agent | `agent.write apps.config.read apps.config.write apps.install apps.read apps.remove apps.upgrade apps.write audit.read backups.create backups.delete backups.read backups.restore capability.write catalog.inspect catalog.publish catalog.verify diagnosis.read diagnosis.write dns.credentials.read dns.credentials.write dns.write domains.read domains.write firewall.read firewall.write identity.write logs.read nsites.admin nsites.publish nsites.read server.read services.read services.restart services.write settings.read settings.write state.write system.migrate system.power system.update system.upgrade users.delete users.read users.write` |
| `c2bc006772cb6b5880475b8949631023c91da9e9adce084a7ad036e95ce14825` | agent | `apps.read domains.read server.read services.read` |
| `d8d7bf7fb1fe94490d6beb8fbb395dc52154d28abf24091c40e6f215055ddac0` | agent | `nsites.read` |
| `ba0b80d39f68b49584a0e57472bde35aad0008a7e02381990c84e86af9390174` | agent | `services.read` |
| `55cd92158f17c2eaa3d96d799d52f6a2c66878ca1fee6071630bfbe6ead553ac` | admin | `apps.config.read apps.config.write apps.install apps.read apps.remove apps.upgrade apps.write audit.read backups.create backups.delete backups.read backups.restore catalog.inspect catalog.publish catalog.verify diagnosis.read dns.credentials.read dns.credentials.write dns.write domains.read domains.write firewall.read firewall.write logs.read server.read services.read services.restart services.write state.write system.migrate system.update system.upgrade users.delete users.read users.write` |

## 1. Generate a fresh 5-key bundle

Generate four new keys (server, operator, publisher, notifier) and keep the
current `notice_sk`. Bundle format must match `keys.recovery`:

```sh
/opt/nostrhost/venv/bin/python - <<'PY'
import secrets, re
from pathlib import Path
# keep the (unexposed) notice key; it is not being rotated
cur = Path("/etc/nostrhost/operator.toml").read_text()
notice_sk = re.search(r'notice_sk\s*=\s*"([0-9a-f]{64})"', cur)
notice_sk = notice_sk.group(1) if notice_sk else secrets.token_hex(32)

keys = {
    "operator_sk": secrets.token_hex(32),
    "server_sk":   secrets.token_hex(32),
    "notice_sk":   notice_sk,
    "publisher_sk":secrets.token_hex(32),
    "notifier_sk": secrets.token_hex(32),
}
bundle = Path("/root/keys-rotation.toml")
bundle.write_text(
    "# nostrhost keys rotation bundle - STORE OFFLINE\n[keys]\n"
    + "\n".join(f'{k} = "{v}"' for k, v in keys.items())
    + "\n"
)
bundle.chmod(0o600)
print("wrote", bundle, "- print/store offline")
PY
```

**Print the bundle once and store it offline** (store-offline label), then keep
the file for step 2. The four new secrets never appear in this runbook.

## 2. Restore the new keys

```sh
nostrhost postinstall restore --keys-file /root/keys-rotation.toml
```

This rewrites `operator.toml`, the control-relay allowlist (`relay.toml`),
`catalogue.env`, `notify.toml`, and `keys.recovery`. Verify the pubkeys changed:

```sh
grep -cE "^#? (server|operator|publisher|notifier)_sk" /etc/nostrhost/operator.toml
```

## 3. Restart key-holding services

```sh
systemctl restart nostrhost-control nostr-api nostr-portal-api nostr-identityd \
  nostr-permissiond nostr-operationsd nostrhost-catalog nostrhost-notify \
  nostrhost-mcp nostr-ddnswatchd nostr-securityd
systemctl --failed --no-pager
```

## 4. Re-link the operator identity

Derive the new operator pubkey (from the new `operator_sk`), then:

```sh
nostrhost identity link nostrhost <NEW_OPERATOR_NPUB> --signer-type nip07 --label operator
nostrhost identity revoke 55cd92158f17c2eaa3d96d799d52f6a2c66878ca1fee6071630bfbe6ead553ac
nostrhost identity list
```

The list must show the new operator pubkey linked/enabled and the old one gone.

## 5. Re-issue capability grants

Re-issue the grants captured in step 0 **verbatim** (they were signed by the
old operator and are now orphaned):

```sh
nostrhost capability grant 3e524b68ace3781786e0031ed35ca8e38baa4e5ecb1598114ae32dd30561d975 \
  agent.write apps.config.read apps.config.write apps.install apps.read apps.remove apps.upgrade \
  apps.write audit.read backups.create backups.delete backups.read backups.restore capability.write \
  catalog.inspect catalog.publish catalog.verify diagnosis.read diagnosis.write dns.credentials.read \
  dns.credentials.write dns.write domains.read domains.write firewall.read firewall.write identity.write \
  logs.read nsites.admin nsites.publish nsites.read server.read services.read services.restart \
  services.write settings.read settings.write state.write system.migrate system.power system.update \
  system.upgrade users.delete users.read users.write --type agent

nostrhost capability grant c2bc006772cb6b5880475b8949631023c91da9e9adce084a7ad036e95ce14825 \
  apps.read domains.read server.read services.read --type agent

nostrhost capability grant d8d7bf7fb1fe94490d6beb8fbb395dc52154d28abf24091c40e6f215055ddac0 \
  nsites.read --type agent

nostrhost capability grant ba0b80d39f68b49584a0e57472bde35aad0008a7e02381990c84e86af9390174 \
  services.read --type agent

nostrhost capability grant <NEW_OPERATOR_PUBKEY> \
  apps.config.read apps.config.write apps.install apps.read apps.remove apps.upgrade apps.write \
  audit.read backups.create backups.delete backups.read backups.restore catalog.inspect catalog.publish \
  catalog.verify diagnosis.read dns.credentials.read dns.credentials.write dns.write domains.read \
  domains.write firewall.read firewall.write logs.read server.read services.read services.restart \
  services.write state.write system.migrate system.update system.upgrade users.delete users.read \
  users.write --type admin
```

Verify with the step-0 snippet (now listing grants signed by the new operator).

## 6. Verify

- `nostrhost identity list` — new operator linked, old revoked.
- The step-0 `list_capabilities` snippet returns the same grant inventory.
- MCP: an `audit.list` / `logs.problems` round-trip succeeds (no
  `catalog_digest_mismatch`, no capability rejection).
- Portal/admin login with the `8c2e62…` signer still works.
- `systemctl --failed` is empty.

## 7. Post-rotation

- Store the **new** bundle (printed in step 1) offline alongside the updated
  `/etc/nostrhost/keys.recovery`. Deleting the offline copy means losing the
  node.
- The opencode MCP client key (`3e524b68…`) and the user signer (`8c2e62…`)
  were not compromised and do not need rotation — only their grants/links,
  already re-issued above.
- Optional hardening: after rotation, delete `/root/keys-rotation.toml`.