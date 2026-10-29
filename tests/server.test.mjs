import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';

test('preview serves all entry assets and keeps project files private', { timeout: 10000 }, async () => {
  const child = spawn(process.execPath, ['scripts/serve.mjs'], { cwd: new URL('../', import.meta.url), env: { ...process.env, PORT: '0' }, windowsHide: true });
  try {
    const url = await new Promise((resolve, reject) => {
      child.once('error', reject);
      child.once('exit', code => reject(new Error(`Server exited: ${code}`)));
      let output = '';
      child.stdout.on('data', chunk => {
        output += chunk;
        const match = output.match(/http:\/\/127\.0\.0\.1:\d+/);
        if (match) resolve(match[0]);
      });
    });
    for (const asset of ['/', '/app.js', '/state.js', '/styles.css', '/orchard.svg']) {
      const response = await fetch(url + asset);
      assert.equal(response.status, 200, asset);
      assert.ok((await response.text()).length > 0, asset);
    }
    assert.equal((await fetch(url + '/missing')).status, 404);
    assert.equal((await fetch(url + '/..%5cpackage.json')).status, 403);
  } finally {
    child.kill();
  }
});
