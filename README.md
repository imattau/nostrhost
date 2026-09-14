# NostrHost

**Run your own little corner of the internet — no username, no password,
no company in between.**

NostrHost turns a cheap server (or an old computer at home) into a personal
hosting platform. Instead of logging in with a username and password, you
log in with a **Nostr key** — the same kind of key used for decentralised
social apps. That key *is* your identity, and every action you take on your
server — installing an app, approving a change, adding a user — is signed
with it, so there's always a clear, tamper-proof record of who did what.

Under the hood, NostrHost is built on [YunoHost](https://yunohost.org/), a
mature and well-tested self-hosting engine used by thousands of people — so
the parts that keep your server safe and reliable (backups, security
updates, TLS certificates) are proven technology, not an untested rewrite.

## Why would I want this?

- **You own it.** Your apps, your data, your server. No platform can lock
  you out, change the rules, or shut you down.
- **No passwords to lose.** You sign in with your Nostr key, the same one
  you might already use for a Nostr social app. Lose a password database
  breach, forgotten-password email, or "reset your password" scam — there
  isn't one.
- **Everything is auditable.** Because every admin action is a signed
  event, you (or anyone you trust) can see exactly what changed on your
  server and when.
- **It's still familiar.** If you've used a control panel before, the
  app store, domains, backups and user-management screens will feel
  familiar — just with a different front door.

## Is it ready for me right now?

**Not yet — NostrHost is pre-alpha.** The pieces exist and mostly work, but
we're still smoothing out the full install → use → recover journey. Right
now it's best suited to people happy to try it on a spare or disposable
machine and tell us what breaks. If that's not you yet, star the repo and
check back — or read [`docs/ALPHA-PLAN.md`](docs/ALPHA-PLAN.md) to see how
close we are.

## What you'll need

- A server or virtual machine running **Debian 12**, or a spare computer
  you're happy to wipe and dedicate to this.
- A domain name (even a free dynamic one works while you're trying it out).
- Your own Nostr key (an `npub`/`nsec` pair) to log in with — any Nostr app
  or browser extension can create one for you in a few seconds. The key you
  sign in with the first time becomes the server's owner. (The server also
  generates its own separate Nostr identity automatically on first run, for
  its internal control-plane relay — that one's not for you to log in with,
  it's the server talking to itself.)

## Installing it

The easiest way is the **automated installer image**: it produces a
ready-to-boot Debian ISO that installs and sets up NostrHost with almost no
input from you. See [`docs/guide/getting-started.md`](docs/guide/getting-started.md)
for the full walkthrough, including the APT-based install if you'd rather
add NostrHost to a server you've already set up.

## Want to go deeper?

- **Using NostrHost day to day?** → the [user guide](docs/guide/README.md)
- **Running a server long-term?** → the [admin guide](docs/admin/README.md)
- **Curious how it's built, or want to contribute code?** → the
  [developer guide](docs/dev/README.md), which covers the repository
  layout, the architecture, and how the pieces fit together
- **Full documentation hub** → [`docs/README.md`](docs/README.md)

## Questions or feedback?

This project is young and changing fast. If something's confusing, broken,
or you just want to say hello, please open an issue — that feedback is what
shapes what gets built next.
