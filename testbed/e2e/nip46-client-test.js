// Raw-ws NIP-46 client test: publish connect request, await response.
const ws = require('ws');
const { nip44, finalizeEvent, getPublicKey, generateSecretKey } = require('nostr-tools');
const [SECRET, PUBKEY] = require('fs').readFileSync('/tmp/login_test_key', 'utf8').trim().split(/\s+/);
const RELAY = 'ws://127.0.0.1:7448';
const KIND = 24133;

const clientSk = generateSecretKey();
const clientPk = getPublicKey(clientSk);
const conv = nip44.getConversationKey(clientSk, PUBKEY);
const content = nip44.v2.encrypt(JSON.stringify({ id: 't1', method: 'connect', params: [PUBKEY, ''] }), conv);
const ev = finalizeEvent({ kind: KIND, tags: [['p', PUBKEY]], content, created_at: Math.floor(Date.now() / 1000) }, clientSk);

const w = new ws(RELAY);
w.on('open', () => {
  w.send(JSON.stringify(['REQ', 'resp', { kinds: [KIND], authors: [PUBKEY], '#p': [clientPk], limit: 10 }]));
  w.send(JSON.stringify(['EVENT', ev]));
  console.log('subscribed + published connect req, clientPk', clientPk.slice(0, 12));
});
w.on('message', (d) => {
  const m = JSON.parse(d.toString());
  if (m[0] === 'EVENT' && m[1] === 'resp') {
    const e = m[2];
    try {
      const pt = nip44.v2.decrypt(e.content, nip44.getConversationKey(clientSk, PUBKEY));
      console.log('GOT RESPONSE:', pt);
      process.exit(0);
    } catch (err) { console.log('decrypt err:', err.message); }
  } else {
    console.log('MSG:', JSON.stringify(m).slice(0, 140));
  }
});
setTimeout(() => { console.log('timeout'); process.exit(1); }, 8000);