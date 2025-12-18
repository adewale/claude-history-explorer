import msgpack from 'msgpack-lite';
import { readFileSync } from 'fs';

const encoded = readFileSync('/tmp/encoded.txt', 'utf-8').trim();
console.log('Encoded length:', encoded.length);

function base64UrlDecode(str) {
  const paddingNeeded = (4 - (str.length % 4)) % 4;
  const padded = str + '='.repeat(paddingNeeded);
  const base64 = padded.replace(/-/g, '+').replace(/_/g, '/');
  const binaryString = Buffer.from(base64, 'base64').toString('binary');
  const bytes = new Uint8Array(binaryString.length);
  for (let i = 0; i < binaryString.length; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return bytes;
}

try {
  const bytes = base64UrlDecode(encoded);
  console.log('Decoded bytes:', bytes.length);

  const raw = msgpack.decode(bytes);
  console.log('Decoded raw keys:', Object.keys(raw));
  console.log('Version:', raw.v);
  console.log('Year:', raw.y);
  console.log('Projects (tp):', raw.tp?.length);
  console.log('Events (te):', raw.te?.length);
  console.log('Fingerprints (sf):', raw.sf?.length);

  // Check structure of first project
  if (raw.tp && raw.tp.length > 0) {
    console.log('First project:', JSON.stringify(raw.tp[0]));
  }

  // Check structure of first event
  if (raw.te && raw.te.length > 0) {
    console.log('First event:', JSON.stringify(raw.te[0]));
  }

  // Check structure of first fingerprint
  if (raw.sf && raw.sf.length > 0) {
    console.log('First fingerprint length:', raw.sf[0]?.length);
    console.log('First fingerprint:', JSON.stringify(raw.sf[0]));
  }

  console.log('\n✅ Decode successful');
} catch (e) {
  console.error('❌ Error:', e.message);
  console.error(e.stack);
}
