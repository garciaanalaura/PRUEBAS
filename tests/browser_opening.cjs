// Optional UI regression: requires Playwright and a local Chromium installation.
// Uses a new temporary database and never opens the real data directory.
const assert = require('node:assert/strict');
const { mkdtempSync, rmSync } = require('node:fs');
const { tmpdir } = require('node:os');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { chromium } = require('playwright');

(async () => {
  const root = path.resolve(__dirname, '..');
  const data = mkdtempSync(path.join(tmpdir(), 'clara-opening-ui-'));
  const python = process.env.CLARA_PYTHON || path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
  const port = process.env.CLARA_TEST_PORT || '8091';
  const base = `http://127.0.0.1:${port}`;
  const server = spawn(python, ['-u', 'app.py'], { cwd: root, env: { ...process.env, RRHH_DATA: data, RRHH_HOST: '127.0.0.1', RRHH_PORT: port, RRHH_HTTPS: '0' }, stdio: ['ignore', 'pipe', 'pipe'] });
  let output = ''; server.stdout.on('data', b => output += b); server.stderr.on('data', b => output += b);
  let browser;
  try {
    let ready = false;
    for (let i = 0; i < 100; i++) {
      if (server.exitCode !== null) throw new Error(output);
      try { if ((await fetch(base)).ok) { ready = true; break; } } catch {}
      await new Promise(r => setTimeout(r, 100));
    }
    assert(ready, output || 'Servidor no disponible');
    browser = await chromium.launch({ headless: true, ...(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {}), args: ['--no-sandbox'] });
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [];page.on('pageerror', e => errors.push(e.message));
    page.on('dialog', d => d.accept());
    await page.goto(base);
    await page.locator('#login [name=username]').fill('admin');
    await page.locator('#login [name=password]').fill('prueba-segura-1234');
    await page.locator('#login button').click();
    await page.locator('#app').waitFor({ state: 'visible' });
    await page.locator('[data-view=employees]').click();
    await page.locator('#new-employee').click();
    for (const [name, value] of Object.entries({ code: 'TEST-1', first: 'Ana', last: 'Prueba', sector: 'RRHH', position: 'Analista', hired: '2010-01-01' })) await page.locator(`#editor [name=${name}]`).fill(value);
    const save = async () => { await page.locator('#editor button.primary').click(); await page.waitForFunction(()=>!document.querySelector('#modal').open||document.querySelector('#form-error')?.textContent||[...document.querySelector('#editor').elements].some(x=>x.validity&&!x.validity.valid)); if(await page.locator('#modal').isVisible())throw Error(await page.locator('#form-error').innerText()+' INVALID: '+await page.locator('#editor').evaluate(f=>[...f.elements].filter(x=>x.validity&&!x.validity.valid).map(x=>x.name+': '+x.validationMessage).join('; ')));  };
    const detail = async () => { await page.locator('[data-employee]').first().click(); await page.locator('#opening-balance').waitFor(); };
    await save();await detail();await page.locator('#opening-balance').click();
    const loaded=page.waitForResponse(r=>r.url().endsWith('/api/data?year=2025'));
    await page.locator('#editor [name=year]').fill('2025');await loaded;
    await page.locator('#editor [name=remaining]').fill('7');
    await page.locator('#editor [name=cutoff]').fill('2025-10-31');
    await page.locator('#editor [name=reason]').fill('Saldo real de prueba');
    await page.locator('#editor [name=confirm]').check();await save();
    const snapshot = () => page.evaluate(async () => (await (await fetch('/api/data?year=2025')).json()).employees[0].balance);
    assert.equal((await snapshot()).available, 7);
    await detail();await page.locator('#employee-history').click();
    await page.locator('#editor [name=start]').fill('2025-08-01');
    await page.locator('#editor [name=end]').fill('2025-08-07');await save();
    let b = await snapshot();assert.equal(b.available, 7);assert.equal(b.included_used, 7);
    await detail();assert((await page.locator('#modal-body').innerText()).includes('no se vuelven a descontar'));
    await page.locator('#employee-history').click();
    await page.locator('#editor [name=start]').fill('2025-11-01');
    await page.locator('#editor [name=end]').fill('2025-11-03');await save();
    b = await snapshot();assert.equal(b.available, 4);assert.equal(b.deducted_used, 3);
    await detail();await page.locator('#edit-balance').click();
    const response=page.waitForResponse(r=>r.url().endsWith('/api/data?year=2024'));
    await page.locator('#editor [name=year]').fill('2024');
    await page.locator('#editor [name=year]').dispatchEvent('change');await response;
    await page.locator('#editor [name=assigned]').fill('10');await page.locator('#editor [name=reason]').fill('Asignación exacta período anterior');await save();
    assert.equal((await snapshot()).available, 4);
    const previous=await page.evaluate(async()=> (await (await fetch('/api/data?year=2024')).json()).employees[0].balance);
    assert.equal(previous.assigned,10);assert.equal(previous.available,10);
    const refreshed=page.waitForResponse(r=>r.url().endsWith('/api/data?year=2025'));
    await page.locator('#year').fill('2025');await page.locator('#year').dispatchEvent('change');await refreshed;await detail();
    // The past-vacation form must offer a lossless switch to future vacations.
    await page.locator('#close').click();await page.locator('[data-view=absences]').click();await page.locator('#new-history').click();
    const futureYear=new Date().getFullYear()+1,start=`${futureYear}-12-14`,end=`${futureYear}-12-15`;
    assert(await page.locator('#editor [name=end]').getAttribute('max'));
    await page.locator('#editor [name=start]').fill(start);
    await page.locator('#editor [name=notes]').fill('Conservar al cambiar de modo');
    await page.locator('#editor [name=entry_mode]').selectOption('normal');
    assert.equal(await page.locator('#editor [name=start]').inputValue(),start);
    assert.equal(await page.locator('#editor [name=notes]').inputValue(),'Conservar al cambiar de modo');
    assert.equal(await page.locator('#editor [name=state]').inputValue(),'Solicitadas');
    assert.equal(await page.locator('#editor [name=end]').getAttribute('max'),null);
    assert.equal(await page.locator('#editor [name=start]').getAttribute('max'),null);
    await page.locator('#editor [name=end]').fill(end);
    assert.equal(await page.locator('#editor [name=end]').getAttribute('min'),start);
    await page.locator('#editor [name=state]').selectOption('Aprobadas');
    await page.locator('#editor [name=approved]').fill(new Date().toISOString().slice(0,10));
    await page.locator('#editor [name=approver]').fill('RRHH de prueba');await save();
    b=await snapshot();assert.equal(b.reserved,2);assert.equal(b.available,2);assert.equal(b.used,10);
    console.log('OK: cambio de historial a vacaciones futuras conserva datos, habilita fecha final futura y reserva 2 días sin marcarlos como disfrutados.');
    await page.locator('[data-view=employees]').click();await page.locator('[data-accrual]').first().click();
    await page.locator('#editor [name=asof]').fill('2025-10-31');
    await page.locator('#editor [name=worked_days]').fill('20');
    await page.locator('#editor [name=acquired]').fill('1');
    await page.locator('#editor [name=assigned]').fill('14');
    await page.locator('#editor [name=reason]').fill('Validación de RRHH ficticia');await save();
    b=await snapshot();assert.equal(b.accrual.acquired,1);assert.equal(b.assigned,14);assert.equal(b.available,2);
    await detail();await page.locator('#edit-accrual').waitFor();
    assert((await page.locator('#modal-body').innerText()).includes('Correspondientes al período / cierre'));
    console.log('OK: adquiridos manuales y asignación anual separados, edición desde nómina y saldo inicial conservado.');
    if(process.env.CLARA_SCREENSHOT)await page.screenshot({path:process.env.CLARA_SCREENSHOT,fullPage:true});
    assert.deepEqual(errors, []);
    console.log('OK: saldo real 7; historial anterior conserva 7; vacaciones posteriores dejan 4; asignación editable de otro año conserva ambos períodos; sin errores JavaScript.');
  } finally {
    if(browser)await browser.close();
    const stopped=new Promise(resolve=>server.once('exit',resolve));
    if(server.exitCode===null){server.kill();await stopped;}
    rmSync(data,{recursive:true,force:true});
  }
})().catch(e=>{console.error(e);process.exitCode=1;});
