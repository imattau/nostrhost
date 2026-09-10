# NostrHost test app

This is the deliberately minimal YunoHost package used to exercise the
NostrHost catalogue, installer, portal, permissions, and SSO migration path.
It installs one static page and no daemon, database, external dependency, or
network service.

The permission declares `auth_request = true` and its NGINX template includes
`nostrhost_auth_request_params`. Existing YunoHost releases that do not know
that permission field will reject the package; that is intentional for this
development fixture.

`catalog.toml` is publisher input, not a signed event. Its revision and hashes
are pinned to the checked-in package for the VM integration test; the content
hash covers the package payload while excluding this publisher-input file.
