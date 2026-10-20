/* =========================================================================
   CloudyAI — AI spend audit
   Reads a usage export entirely in the browser, looks for cacheable
   repetition and model-tier mismatch, and reports how complete the logging
   is. No network calls, no dependencies.
   ========================================================================= */
(function () {
  'use strict';

  if (!document.getElementById('dropZone')) return;

  var el = {
    upload: document.getElementById('uploadStage'),
    analyzing: document.getElementById('analyzingStage'),
    results: document.getElementById('resultsStage'),
    drop: document.getElementById('dropZone'),
    file: document.getElementById('fileInput'),
    paste: document.getElementById('pasteArea'),
    err: document.getElementById('auditError'),
    lowConf: document.getElementById('lowConfidence'),
    missing: document.getElementById('missingCols'),
    headline: document.getElementById('headlineValue'),
    headlineSub: document.getElementById('headlineSub'),
    models: document.getElementById('modelBreakdown'),
    caching: document.getElementById('cachingFindings'),
    routing: document.getElementById('routingFindings'),
    governance: document.getElementById('governanceChecks')
  };

  var HEADER_ALIASES = {
    model: ['model', 'model_name', 'model_id'],
    tokensIn: ['tokens_in', 'input_tokens', 'prompt_tokens', 'tokensin'],
    tokensOut: ['tokens_out', 'output_tokens', 'completion_tokens', 'tokensout'],
    timestamp: ['timestamp', 'created_at', 'time', 'date', 'datetime'],
    cost: ['cost', 'cost_usd', 'total_cost', 'amount', 'spend']
  };

  /* ------------------------------------------------------------- utilities */
  function esc(value) {
    return String(value).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function fmtUSD(n) {
    return n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 });
  }
  function fmtInt(n) {
    return n.toLocaleString('en-US');
  }
  function findCol(headers, aliases) {
    var lower = headers.map(function (h) { return h.trim().toLowerCase(); });
    for (var i = 0; i < aliases.length; i++) {
      var idx = lower.indexOf(aliases[i]);
      if (idx !== -1) return idx;
    }
    return -1;
  }

  /* ---------------------------------------------------------------- parsing */
  function parseCSV(text) {
    var lines = text.split(/\r?\n/).map(function (l) { return l.trim(); }).filter(Boolean);
    if (lines.length < 2) throw new Error('That file does not have enough rows.');

    var headers = lines[0].split(',').map(function (h) { return h.replace(/^"|"$/g, ''); });
    var col = {
      model: findCol(headers, HEADER_ALIASES.model),
      tokensIn: findCol(headers, HEADER_ALIASES.tokensIn),
      tokensOut: findCol(headers, HEADER_ALIASES.tokensOut),
      timestamp: findCol(headers, HEADER_ALIASES.timestamp),
      cost: findCol(headers, HEADER_ALIASES.cost)
    };
    var missing = Object.keys(col).filter(function (k) { return col[k] === -1; });
    if (missing.length === 5) {
      throw new Error('None of the expected columns were found in the header row.');
    }

    var rows = [];
    for (var i = 1; i < lines.length; i++) {
      var cells = (lines[i].match(/(".*?"|[^,]+)(?=,|$)/g) || []).map(function (c) {
        return c.replace(/^"|"$/g, '').trim();
      });
      var row = {
        model: col.model !== -1 ? cells[col.model] : 'unknown',
        tokensIn: col.tokensIn !== -1 ? Number(cells[col.tokensIn]) || 0 : 0,
        tokensOut: col.tokensOut !== -1 ? Number(cells[col.tokensOut]) || 0 : 0,
        timestamp: col.timestamp !== -1 ? cells[col.timestamp] : null,
        cost: col.cost !== -1 ? Number(String(cells[col.cost]).replace(/[^0-9.\-]/g, '')) || 0 : 0
      };
      var hasModel = col.model !== -1 && row.model && row.model.length > 0;
      var hasNumber = row.cost > 0 || row.tokensIn > 0 || row.tokensOut > 0;
      if (hasModel || hasNumber) rows.push(row);
    }
    if (!rows.length) throw new Error('No usable rows were found in that file.');
    return { rows: rows, missing: missing };
  }

  /* --------------------------------------------------------------- analysis */
  function tier(modelName) {
    var m = (modelName || '').toLowerCase();
    if (m.indexOf('opus') !== -1) return 'premium';
    if (m.indexOf('sonnet') !== -1) return 'mid';
    if (m.indexOf('haiku') !== -1) return 'economy';
    return 'unknown';
  }
  function tierColour(t) {
    if (t === 'premium') return '#a4421d';
    if (t === 'mid') return '#b3873a';
    return '#48573f';
  }

  function analyse(rows) {
    var totalCost = 0;
    var byModel = {};

    rows.forEach(function (r) {
      totalCost += r.cost;
      if (!byModel[r.model]) byModel[r.model] = { cost: 0, calls: 0 };
      byModel[r.model].cost += r.cost;
      byModel[r.model].calls += 1;
    });

    var modelBreakdown = Object.keys(byModel).map(function (name) {
      return { model: name, cost: byModel[name].cost, calls: byModel[name].calls };
    }).sort(function (a, b) { return b.cost - a.cost; });

    /* caching: similarly sized inputs to the same model, five or more times */
    var BUCKET = 200;
    var buckets = {};
    rows.forEach(function (r) {
      var bucket = Math.round(r.tokensIn / BUCKET) * BUCKET;
      var key = r.model + '::' + bucket;
      if (!buckets[key]) buckets[key] = { model: r.model, bucket: bucket, calls: 0, cost: 0 };
      buckets[key].calls += 1;
      buckets[key].cost += r.cost;
    });
    var clusters = Object.keys(buckets).map(function (k) { return buckets[k]; })
      .filter(function (b) { return b.calls >= 5; })
      .sort(function (a, b) { return b.cost - a.cost; });

    var cacheableCost = clusters.reduce(function (s, b) { return s + b.cost; }, 0);
    var CACHE_RATE = 0.6;
    var cacheSavings = cacheableCost * CACHE_RATE;

    /* routing: premium-tier calls with tiny outputs */
    var SMALL_OUTPUT = 300;
    var routingCandidates = rows.filter(function (r) {
      return tier(r.model) === 'premium' && r.tokensOut > 0 && r.tokensOut < SMALL_OUTPUT;
    });
    var routingCandidateCost = routingCandidates.reduce(function (s, r) { return s + r.cost; }, 0);

    /* do not count the same dollars twice: caching is attributed first */
    var cacheableKeys = {};
    clusters.forEach(function (b) { cacheableKeys[b.model + '::' + b.bucket] = true; });
    var routingOnlyCost = rows.reduce(function (s, r) {
      var candidate = tier(r.model) === 'premium' && r.tokensOut > 0 && r.tokensOut < SMALL_OUTPUT;
      if (!candidate) return s;
      var bucket = Math.round(r.tokensIn / BUCKET) * BUCKET;
      if (cacheableKeys[r.model + '::' + bucket]) return s;
      return s + r.cost;
    }, 0);
    var ROUTING_RATE = 0.7;
    var routingSavings = routingOnlyCost * ROUTING_RATE;

    /* governance signals */
    var hasTimestamps = rows.some(function (r) { return r.timestamp; });
    var suspiciousGap = false;
    var gapDays = 0;
    if (hasTimestamps) {
      var times = rows.map(function (r) { return new Date(r.timestamp).getTime(); })
        .filter(function (t) { return !isNaN(t); })
        .sort(function (a, b) { return a - b; });
      if (times.length > 1) {
        var span = (times[times.length - 1] - times[0]) / 86400000;
        var avg = span / times.length;
        var maxGap = 0;
        for (var i = 1; i < times.length; i++) {
          maxGap = Math.max(maxGap, times[i] - times[i - 1]);
        }
        gapDays = maxGap / 86400000;
        suspiciousGap = avg > 0 && gapDays > avg * 5 && gapDays > 1;
      }
    }

    var hasCost = rows.some(function (r) { return r.cost > 0; });
    var attributable = modelBreakdown.every(function (m) { return m.model !== 'unknown'; });

    var governance = [
      {
        label: 'Per-model attribution',
        pass: attributable,
        note: attributable
          ? 'Every call in this export can be tied to a specific model.'
          : 'Some rows have no identifiable model, so their cost cannot be attributed to a feature.'
      },
      {
        label: 'Timestamp coverage',
        pass: hasTimestamps,
        note: hasTimestamps
          ? 'Usage is time-stamped, so trends and anomalies are traceable.'
          : 'No usable timestamps: you can tell that spend happened, not when.'
      },
      {
        label: 'Continuous logging',
        pass: hasTimestamps && !suspiciousGap,
        note: !hasTimestamps
          ? 'Cannot be assessed without timestamps.'
          : suspiciousGap
            ? 'A gap of roughly ' + gapDays.toFixed(1) + ' days appears in this export. Something may be spending elsewhere.'
            : 'No unexplained silent gaps in this export.'
      },
      {
        label: 'Row-level cost',
        pass: hasCost,
        note: hasCost
          ? 'Cost is available per call, so spend is auditable at row level.'
          : 'No usable cost values: spend cannot be reconciled from this export alone.'
      }
    ];

    var totalLeak = cacheSavings + routingSavings;
    return {
      totalCost: totalCost,
      totalCalls: rows.length,
      modelBreakdown: modelBreakdown,
      clusters: clusters,
      cacheableCost: cacheableCost,
      cacheSavings: cacheSavings,
      routingCandidates: routingCandidates,
      routingCandidateCost: routingCandidateCost,
      routingOnlyCost: routingOnlyCost,
      routingSavings: routingSavings,
      governance: governance,
      totalLeak: totalLeak,
      leakPercent: totalCost > 0 ? (totalLeak / totalCost) * 100 : 0,
      lowConfidence: rows.length < 30
    };
  }

  /* ------------------------------------------------------------ sample data */
  function sampleCSV() {
    var rows = [];
    function push(model, tIn, tOut, cost, day, hour, minute) {
      var d = String(day).padStart(2, '0');
      rows.push([model, tIn, tOut,
        '2026-06-' + d + 'T' + String(hour).padStart(2, '0') + ':' + String(minute).padStart(2, '0') + ':00Z',
        cost.toFixed(3)].join(','));
    }

    /* A large static prefix (a policy document, a product catalogue) resent on
       every call: same input size, 24 times — the classic caching case. */
    for (var i = 0; i < 10; i++) {
      push('claude-opus-4-1', 4100 + (i % 5) * 22, 1720 + (i % 7) * 140, 0.58 + (i % 5) * 0.02,
        1 + (i % 9), 9 + (i % 8), (i * 7) % 60);
    }

    /* Premium tier, tiny outputs, varied inputs — a classification job that
       never needed the top model. */
    for (i = 0; i < 34; i++) {
      push('claude-opus-4-1', 620 + i * 271, 45 + (i % 4) * 18, 0.068 + (i % 3) * 0.006,
        1 + (i % 14), 10 + (i % 6), (i * 11) % 60);
    }

    /* A reasonable mid-tier workload: varied prompts, substantial outputs. */
    for (i = 0; i < 34; i++) {
      push('claude-sonnet-4-5', 2600 + i * 137, 640 + (i % 6) * 310, 0.19 + (i % 6) * 0.04,
        3 + (i % 12), 11 + (i % 7), (i * 13) % 60);
    }

    /* Cheap, appropriate use of the small model. */
    for (i = 0; i < 22; i++) {
      push('claude-haiku-4-5', 460 + i * 97, 140 + (i % 3) * 90, 0.014 + (i % 3) * 0.004,
        5 + (i % 10), 9 + (i % 9), (i * 17) % 60);
    }

    return 'model,tokens_in,tokens_out,timestamp,cost\n' + rows.join('\n');
  }

  /* --------------------------------------------------------------- rendering */
  function countUp(node, target) {
    var start = performance.now();
    var duration = 1200;
    function frame(now) {
      var t = Math.min(1, (now - start) / duration);
      var eased = 1 - Math.pow(1 - t, 3);
      node.textContent = fmtUSD(target * eased);
      if (t < 1) requestAnimationFrame(frame);
      else node.textContent = fmtUSD(target);
    }
    requestAnimationFrame(frame);
  }

  function showStage(name) {
    el.upload.classList.toggle('is-visible', name === 'upload');
    el.analyzing.classList.toggle('is-visible', name === 'analyzing');
    el.results.classList.toggle('is-visible', name === 'results');
  }

  function showError(message) {
    el.err.textContent = message + ' Expected columns: model, tokens_in, tokens_out, timestamp, cost — try the sample data to see the shape.';
    el.err.classList.add('is-visible');
  }
  function clearError() {
    el.err.textContent = '';
    el.err.classList.remove('is-visible');
  }

  function render(result, missing) {
    showStage('results');

    el.lowConf.classList.toggle('is-visible', result.lowConfidence);
    if (result.lowConfidence) {
      el.lowConf.textContent = 'Only ' + fmtInt(result.totalCalls) +
        ' calls in this export. The estimate is directional, not a confident number — a full month of usage sharpens it considerably.';
    }

    var hasMissing = missing && missing.length > 0;
    el.missing.classList.toggle('is-visible', hasMissing);
    if (hasMissing) {
      el.missing.textContent = 'Could not find these columns: ' + missing.join(', ') +
        '. The analysis used what was available and defaulted the rest.';
    }

    countUp(el.headline, result.totalLeak);

    var tone = result.leakPercent > 25 ? '#a4421d' : result.leakPercent > 10 ? '#b3873a' : '#48573f';
    el.headlineSub.innerHTML = 'About <strong style="color:' + tone + '">' +
      result.leakPercent.toFixed(0) + '%</strong> of the ' + fmtUSD(result.totalCost) +
      ' in this export, across ' + fmtInt(result.totalCalls) + ' calls and ' +
      result.modelBreakdown.length + ' model' + (result.modelBreakdown.length === 1 ? '' : 's') +
      ' — from traffic that looks cacheable or over-routed to a pricier model than the task needed.';

    el.models.innerHTML = result.modelBreakdown.map(function (m) {
      var pct = result.totalCost > 0 ? (m.cost / result.totalCost) * 100 : 0;
      return '<div class="model-row">' +
        '<div class="model-row__name" title="' + esc(m.model) + '">' + esc(m.model) + '</div>' +
        '<div class="model-row__track"><div class="model-row__fill" style="width:' + pct.toFixed(1) +
          '%;background:' + tierColour(tier(m.model)) + '"></div></div>' +
        '<div class="model-row__cost">' + fmtUSD(m.cost) + '</div>' +
        '<div class="model-row__calls">' + fmtInt(m.calls) + '×</div>' +
        '</div>';
    }).join('');

    if (!result.clusters.length) {
      el.caching.innerHTML = '<div class="finding finding--empty">No clusters of repeated, similarly sized calls stood out. Either the traffic is genuinely varied, or the sample is too small to tell.</div>';
    } else {
      var clusterCalls = result.clusters.reduce(function (s, c) { return s + c.calls; }, 0);
      el.caching.innerHTML =
        '<div class="finding"><div><p class="finding__label">Likely cacheable spend</p>' +
        '<p class="finding__detail">' + result.clusters.length + ' pattern' +
        (result.clusters.length === 1 ? '' : 's') + ' of repeated, similar-sized input across ' +
        fmtInt(clusterCalls) + ' calls.</p></div>' +
        '<div class="finding__value">' + fmtUSD(result.cacheableCost) + '</div></div>' +
        '<div class="finding"><div><p class="finding__label">Estimated saving with prompt caching</p>' +
        '<p class="finding__detail">Conservative: a 60% saving on that spend. Actual savings depend on how identical the repeated content really is.</p></div>' +
        '<div class="finding__value is-accent">' + fmtUSD(result.cacheSavings) + '</div></div>';
    }

    if (!result.routingCandidates.length) {
      el.routing.innerHTML = '<div class="finding finding--empty">No premium-tier calls with unusually small output were flagged. Model choice looks reasonably matched to task size.</div>';
    } else {
      var overlapNote = result.routingOnlyCost === 0
        ? 'All of this spend is already counted under caching above. Fixing the repetition resolves this too, so no separate saving is added.'
        : 'Excludes spend already counted under caching, so the two estimates do not overlap.';
      el.routing.innerHTML =
        '<div class="finding"><div><p class="finding__label">Premium calls with small output</p>' +
        '<p class="finding__detail">' + fmtUSD(result.routingCandidateCost) + ' spent on calls returning under 300 tokens — often a sign the task did not need the top tier.</p></div>' +
        '<div class="finding__value">' + fmtInt(result.routingCandidates.length) + ' calls</div></div>' +
        '<div class="finding"><div><p class="finding__label">Estimated saving by right-sizing</p>' +
        '<p class="finding__detail">' + overlapNote + '</p></div>' +
        '<div class="finding__value is-accent">' + fmtUSD(result.routingSavings) + '</div></div>';
    }

    el.governance.innerHTML = result.governance.map(function (c) {
      return '<div class="gov-row">' +
        '<div class="gov-icon ' + (c.pass ? 'is-pass' : 'is-fail') + '">' + (c.pass ? '✓' : '!') + '</div>' +
        '<div><p class="gov-label">' + c.label + '</p><p class="gov-note">' + c.note + '</p></div>' +
        '</div>';
    }).join('');
  }

  function process(text) {
    clearError();
    var parsed;
    try {
      parsed = parseCSV(text);
    } catch (e) {
      showError(e.message || 'That file could not be parsed.');
      return;
    }
    showStage('analyzing');
    window.setTimeout(function () {
      render(analyse(parsed.rows), parsed.missing);
    }, 700);
  }

  function readFile(file) {
    if (!file) return;
    var reader = new FileReader();
    reader.onload = function (ev) { process(String(ev.target.result)); };
    reader.onerror = function () { showError('That file could not be read.'); };
    reader.readAsText(file);
  }

  /* ------------------------------------------------------------------ events */
  el.drop.addEventListener('click', function () { el.file.click(); });
  el.drop.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      el.file.click();
    }
  });
  el.file.addEventListener('change', function (e) {
    var file = e.target.files && e.target.files[0];
    readFile(file);
  });
  ['dragenter', 'dragover'].forEach(function (type) {
    el.drop.addEventListener(type, function (e) {
      e.preventDefault();
      el.drop.classList.add('is-drag');
    });
  });
  ['dragleave', 'drop'].forEach(function (type) {
    el.drop.addEventListener(type, function (e) {
      e.preventDefault();
      el.drop.classList.remove('is-drag');
    });
  });
  el.drop.addEventListener('drop', function (e) {
    var file = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
    readFile(file);
  });

  document.getElementById('runPaste').addEventListener('click', function () {
    var text = el.paste.value.trim();
    if (!text) {
      showError('Paste a few rows first, or use the sample data.');
      return;
    }
    process(text);
  });

  document.getElementById('runSample').addEventListener('click', function () {
    process(sampleCSV());
  });

  document.getElementById('resetAudit').addEventListener('click', function () {
    el.paste.value = '';
    el.file.value = '';
    clearError();
    showStage('upload');
    el.drop.focus();
  });
})();
