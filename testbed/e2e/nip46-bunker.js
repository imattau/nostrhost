#!/usr/bin/env node
// Minimal NIP-46 bunker for the portal E2E, using raw ws (flat REQ format
// the nostrhost relay + the browser's older nostr-tools expect).
const fs = require('fs');
const ws = require('ws');
const { nip44, finalizeEvent, getPublicKey } = require('nostr-tools');

const KEY_FILE = process.env.BUNKER_KEY_FILE || '/tmp/login_test_key';
const [SECRET, PUBKEY] = fs.readFileSync(KEY_FILE, 'utf8').trim().split(/\s+/);
const RELAY = process.env.BUNKER_RELAY || 'ws://127.0.0.1:7448';
const KIND = 24133;
const h2b = (h) => new Uint8Array(Buffer.from(h, 'hex'));

async function handle(ev) {
  let reqId = '0';
  try {
    const conv = nip44.getConversationKey(h2b(SECRET), ev.pubkey);
    const payload = JSON.parse(nip44.v2.decrypt(ev.content, conv));
    reqId = payload.id;
    const { id, method, params } = payload;
    console.log('REQUEST', method, 'from', ev.pubkey.slice(0, 12), 'id', id);
    let result;
    switch (method) {
      case 'connect':
        result = SECRET;
        break;
      case 'get_public_key':
        result = PUBKEY;
        break;
      case 'sign_event': {
        const event = JSON.parse(params[0]);
        console.log('sign_event payload:', JSON.stringify(event).slice(0, 400));
        console.log('sign_event keys:', Object.keys(event).join(','), 'pubkey?', typeof event.pubkey);
        const normalized = { ...event };
        normalized.pubkey = getPublicKey(h2b(SECRET));
        const signed = finalizeEvent(normalized, h2b(SECRET));
        result = JSON.stringify(signed);
        break;
      }
      case 'ping':
        result = 'pong';
        break;
      case 'get_relays':
        result = JSON.stringify([{ url: RELAY, read: true, write: true }]);
        break;
      case 'describe':
        result = JSON.stringify(['connect', 'get_public_key', 'sign_event', 'ping', 'get_relays']);
        break;
      default:
        throw new Error('unknown method ' + method);
    }
    const content = nip44.v2.encrypt(JSON.stringify({ id, result }), conv);
    const signed = finalizeEvent(
      { kind: KIND, tags: [['p', ev.pubkey]], content, created_at: Math.floor(Date.now() / 1000) },
      h2b(SECRET),
    );
    const sock = new ws(RELAY);
    await new Promise((res, rej) => {
      sock.on('open', () => { sock.send(JSON.stringify(['EVENT', signed])); res(); });
      sock.on('error', rej);
    });
    sock.close();
    console.log('RESPONSE', method, 'ok');
  } catch (e) {
    console.log('REQUEST-ERR', e.message);
    try {
      const conv = nip44.getConversationKey(h2b(SECRET), ev.pubkey);
      const content = nip44.v2.encrypt(JSON.stringify({ id: reqId, error: e.message }), conv);
      const signed = finalizeEvent(
        { kind: KIND, tags: [['p', ev.pubkey]], content, created_at: Math.floor(Date.now() / 1000) },
        h2b(SECRET),
      );
      const sock = new ws(RELAY);
      await new Promise((res) => { sock.on('open', () => { sock.send(JSON.stringify(['EVENT', signed])); res(); }); });
      sock.close();
    } catch (_) {}
  }
}

function main() {
  const sock = new ws(RELAY);
  sock.on('open', () => {
    sock.send(JSON.stringify(['REQ', 'bunker', { kinds: [KIND], '#p': [PUBKEY], limit: 0 }]));
    console.log('bunker listening on', RELAY, 'pubkey', PUBKEY.slice(0, 12) + '...');
  });
  sock.on('message', (d) => {
    const m = JSON.parse(d.toString());
    if (m[0] === 'EVENT') {
      handle(m[2]);
    }
  });
  sock.on('error', (e) => console.error('bunker ws error', e.message));
  sock.on('close', () => { console.log('relay closed, reconnecting in 2s'); setTimeout(main, 2000); });
}

main();