// CLI run-code entry. UI submits; subsequent GETs observe only the correlated job.
async page => {
  const origin = 'http://127.0.0.1:18008';
  // The CLI VM has no Web URL global. Accept only this exact absolute origin.
  const pathname = url => typeof url === 'string' && url.startsWith(origin + '/')
    ? url.slice(origin.length).split(/[?#]/, 1)[0] : null;
  if (page.url() !== origin && pathname(page.url()) === null) throw new Error('capture_origin_denied');
  const uuid = value => typeof value === 'string' && /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(value);
  const scalar = value => typeof value === 'string' && /^[A-Za-z0-9_.:-]{1,80}$/.test(value) ? value : 'UNKNOWN';
  const job = await page.evaluate(() => localStorage.getItem('ita.last-local-job'));
  if (!uuid(job)) throw new Error('capture_job_required');
  const root = `/api/trip-plans/${job}/replans`;
  const diagnosticUrl = `${origin}/__r5__/diagnostics?job_id=${job}`;
  const readState = async () => {
    const response = await page.request.get(diagnosticUrl);
    if (response.status() !== 200) throw new Error('capture_diagnostics_unavailable');
    const state = await response.json();
    if (state.job_id !== job || !uuid(state.plan_id) ||
        !Number.isSafeInteger(state.version) || state.version < 1 ||
        !Number.isSafeInteger(state.fault_remaining) || state.fault_remaining < 0) {
      throw new Error('capture_diagnostics_invalid');
    }
    return { plan_id: state.plan_id, version: state.version, fault_remaining: state.fault_remaining };
  };
  const before = await readState();
  const confirm = page.getByRole('button', { name: '确认并生成新版本', exact: true });
  const confirming = await confirm.isVisible();
  const control = confirming ? confirm : page.getByRole('button', { name: '分析影响', exact: true });
  const matches = request => {
    const path = pathname(request.url());
    if (path === null || request.method() !== 'POST') return false;
    if (!confirming) return path === root;
    const suffix = path.slice(root.length + 1).split('/');
    return path.startsWith(root + '/') && suffix.length === 2 && uuid(suffix[0]) && suffix[1] === 'decision';
  };
  const submitted = [];
  const onRequest = request => { if (matches(request)) submitted.push(request); };
  page.on('request', onRequest);
  try {
    // Arm before the click; never match a different job's background response.
    const waiting = page.waitForResponse(response => matches(response.request()), { timeout: 100000 });
    const [response] = await Promise.all([waiting, control.click()]);
    const request = response.request();
    const payload = request.postDataJSON();
    let value;
    try { value = await response.json(); } catch { value = {}; }
    if (!value || typeof value !== 'object') value = {};
    const requestId = confirming ? value.replan_request_id : payload.replan_request_id;
    const replanId = confirming ? pathname(request.url()).split('/').at(-2) : value.replan_id;
    const successfulHttp = response.status() >= 200 && response.status() < 300;
    const verifyIdentity = body => {
      if (!uuid(requestId) || !uuid(replanId) || body.job_id !== job ||
          body.replan_id !== replanId || body.replan_request_id !== requestId) {
        throw new Error('capture_response_mismatch');
      }
    };
    let httpStatus = response.status();
    if (successfulHttp) {
      verifyIdentity(value);
      const deadline = Date.now() + 100000;
      while (value.status === 'analyzing' || value.status === 'replanning') {
        if (Date.now() >= deadline) throw new Error('capture_terminal_timeout');
        await page.waitForTimeout(150);
        const observed = await page.request.get(`${origin}${root}/${replanId}`);
        httpStatus = observed.status();
        try { value = await observed.json(); } catch { value = {}; }
        if (!value || typeof value !== 'object') value = {};
        if (httpStatus !== 200) break;
        verifyIdentity(value);
      }
    }
    if (submitted.length !== 1 || submitted[0] !== request) throw new Error('capture_ambiguous_submission');
    const after = await readState();
    const errors = Array.isArray(value.errors) ? value.errors : value.error ? [value.error] : [];
    return {
      action: confirming ? 'confirm' : 'analyze', http_status: httpStatus,
      request_id: uuid(requestId) ? requestId : 'UNKNOWN', replan_id: uuid(replanId) ? replanId : 'UNKNOWN',
      status: httpStatus >= 400 ? 'HTTP_ERROR' : scalar(value.status),
      before, after, old_plan_unchanged: before.plan_id === after.plan_id && before.version === after.version,
      errors: errors.filter(error => error && typeof error === 'object').slice(0, 10).map(error => ({
        public_code: scalar(error.code), diagnostic_code: scalar(error.diagnostic_code),
        retryable: typeof error.retryable === 'boolean' ? error.retryable : 'UNKNOWN',
      })),
    };
  } finally {
    page.off('request', onRequest);
  }
}
