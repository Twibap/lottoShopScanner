import test from 'node:test';
import assert from 'node:assert/strict';
import { distanceLabel, escapeHtml, nearbyUrl, won } from '../lib.js';

test('formats user-facing values', () => {
  assert.equal(distanceLabel(840), '840m');
  assert.equal(distanceLabel(1250), '1.3km');
  assert.equal(won(1234567), '1,234,567원');
});

test('escapes API-provided text', () => {
  assert.equal(escapeHtml('<script>"x"</script>'), '&lt;script&gt;&quot;x&quot;&lt;/script&gt;');
});

test('builds the unchanged backend contract', () => {
  const url = nearbyUrl({ lat: 37.5, lng: 127, radius: 3000, sort: 'distance' });
  assert.match(url, /^\/api\/v1\/shops\/nearby\?/);
  assert.match(url, /radius_m=3000/);
  assert.match(url, /limit=100/);
});
