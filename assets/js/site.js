/* =========================================================================
   CloudyAI — site behaviour
   No dependencies. Everything here degrades gracefully with JS off.
   ========================================================================= */
(function () {
  'use strict';

  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------------------------------------------------------------- header */
  var header = document.getElementById('siteHeader');
  if (header) {
    var onScroll = function () {
      header.classList.toggle('is-scrolled', window.scrollY > 12);
    };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
  }

  /* ------------------------------------------------------------ mobile menu */
  var menu = document.getElementById('mobileMenu');
  var openBtn = document.getElementById('navToggle');
  var closeBtn = document.getElementById('menuClose');

  function openMenu() {
    if (!menu) return;
    menu.classList.add('is-open');
    menu.setAttribute('aria-hidden', 'false');
    if (openBtn) openBtn.setAttribute('aria-expanded', 'true');
    document.body.style.overflow = 'hidden';
    var first = menu.querySelector('a, button');
    if (first) first.focus();
  }
  function closeMenu() {
    if (!menu) return;
    menu.classList.remove('is-open');
    menu.setAttribute('aria-hidden', 'true');
    if (openBtn) openBtn.setAttribute('aria-expanded', 'false');
    document.body.style.overflow = '';
    if (openBtn) openBtn.focus();
  }
  if (openBtn) openBtn.addEventListener('click', function () {
    if (menu && menu.classList.contains('is-open')) closeMenu();
    else openMenu();
  });
  if (closeBtn) closeBtn.addEventListener('click', closeMenu);
  if (menu) {
    menu.querySelectorAll('a').forEach(function (a) {
      a.addEventListener('click', function () {
        menu.classList.remove('is-open');
        menu.setAttribute('aria-hidden', 'true');
        document.body.style.overflow = '';
        if (openBtn) openBtn.setAttribute('aria-expanded', 'false');
      });
    });
  }
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && menu && menu.classList.contains('is-open')) closeMenu();
  });

  /* ---------------------------------------------------------------- reveal */
  var reveals = document.querySelectorAll('.reveal');
  if (reveals.length) {
    if (reduced || !('IntersectionObserver' in window)) {
      reveals.forEach(function (el) { el.classList.add('is-in'); });
    } else {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-in');
            io.unobserve(entry.target);
          }
        });
      }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
      reveals.forEach(function (el) { io.observe(el); });
    }
  }

  /* ------------------------------------------------------------------ year */
  var year = document.getElementById('year');
  if (year) year.textContent = String(new Date().getFullYear());

  /* =======================================================================
     Detection demo
     Coordinates are percentages of the photograph, measured from the still
     frames in assets/img. They are illustrative, not a live feed.
     ======================================================================= */
  var DEMOS = {
    ppe: {
      img: 'assets/img/cam-ppe.webp',
      alt: 'Ceiling camera view of a packing hall with workers in hi-vis vests, one without a hard hat.',
      cam: 'CAM-04 · packing hall',
      title: 'PPE compliance',
      desc: 'Hard hat and hi-vis checks on a fixed ceiling camera. One alert per person, after a persistence window — not forty alerts per frame.',
      stats: [['Precision', '0.94'], ['Alerts / shift', '3'], ['Latency', '640 ms']],
      feed: [
        ['06:12:04', 'ok', 'Person 03 enters packing hall — <b>helmet and vest</b> detected'],
        ['06:12:06', 'alert', 'Person 07 at the machine: <b>no hard hat</b> for 4 s — alert raised'],
        ['06:12:09', 'ok', 'Clip saved (8 s) · shift supervisor notified on WhatsApp'],
        ['06:12:41', 'watch', 'Person 11 at 21 m: helmet under 50 px — verification skipped']
      ],
      dets: [
        { x: 27.2, y: 40.4, w: 10.6, h: 52.0, cls: 'ok', label: 'person 0.98' },
        { x: 28.4, y: 40.8, w: 8.2, h: 10.4, cls: 'ok', label: 'helmet 0.96' },
        { x: 46.9, y: 35.8, w: 7.2, h: 34.4, cls: 'alert', label: 'person 0.95', tag: 'no hard hat' },
        { x: 37.9, y: 32.2, w: 5.4, h: 27.6, cls: 'ok', label: 'person 0.93' },
        { x: 38.5, y: 31.8, w: 4.2, h: 7.0, cls: 'ok', label: 'helmet 0.91' },
        { x: 26.8, y: 22.9, w: 4.6, h: 16.2, cls: 'watch', label: 'too far', tag: '21 m' }
      ]
    },

    fill: {
      img: 'assets/img/cam-fill.webp',
      alt: 'Backlit bottles on a filling line, two of them visibly underfilled.',
      cam: 'CAM-11 · filler exit',
      title: 'Fill level',
      desc: 'Backlit measurement at line speed. Underfills go to the rejector; the reason goes to the filler-head log, so the next one does not happen.',
      stats: [['Containers / min', '420'], ['Accuracy', '±1.2 mm'], ['False rejects', '0.3%']],
      feed: [
        ['14:02:11', 'alert', 'Bottle 4,182 — fill <b>8.4 mm low</b> → rejector'],
        ['14:02:11', 'ok', 'Bottle 4,183 — fill within tolerance'],
        ['14:02:12', 'alert', 'Bottle 4,197 — fill <b>7.9 mm low</b> → rejector'],
        ['14:02:40', 'watch', '3 rejects in 60 s — filler head 2 flagged for check']
      ],
      dets: [
        { x: 3.8, y: 26.4, w: 5.2, h: 41.0, cls: 'ok', gauge: 33.4 },
        { x: 10.6, y: 26.4, w: 5.2, h: 41.0, cls: 'ok' },
        { x: 17.9, y: 26.4, w: 5.2, h: 41.0, cls: 'ok' },
        { x: 25.3, y: 26.4, w: 5.2, h: 41.0, cls: 'ok' },
        { x: 32.3, y: 26.4, w: 5.2, h: 41.0, cls: 'ok', gauge: 33.6 },
        { x: 46.8, y: 26.4, w: 5.6, h: 41.0, cls: 'alert', gauge: 47.2, label: 'underfill', tag: '8.4 mm' },
        { x: 62.6, y: 26.4, w: 5.2, h: 41.0, cls: 'ok' },
        { x: 69.6, y: 26.4, w: 5.6, h: 41.0, cls: 'alert', gauge: 45.8, label: 'underfill', tag: '7.9 mm' },
        { x: 81.0, y: 26.4, w: 5.2, h: 41.0, cls: 'ok' }
      ]
    },

    assembly: {
      img: 'assets/img/card-assembly.webp',
      alt: 'Hands assembling a circuit board at a brightly lit workbench with component trays.',
      cam: 'CAM-07 · station 12',
      title: 'Assembly verification',
      desc: 'Presence and seating checks at the station. The line holds on a review state — a person decides, not the model.',
      stats: [['Cycle', '38 s'], ['Checks', '4'], ['Escapes', '0']],
      feed: [
        ['09:21:07', 'ok', 'Board present and located — pass'],
        ['09:21:08', 'ok', 'Connector J2 seated — pass'],
        ['09:21:09', 'watch', 'Fastener count <b>3 of 4</b> — station held for review'],
        ['09:21:31', 'ok', 'Operator confirms missing fastener — rework logged']
      ],
      dets: [
        { x: 33.2, y: 64.2, w: 11.8, h: 18.2, cls: 'ok', label: 'board present' },
        { x: 37.2, y: 70.4, w: 5.4, h: 9.0, cls: 'watch', label: 'connector J2', tag: 'review' },
        { x: 46.8, y: 54.4, w: 28.4, h: 24.6, cls: 'ok', label: 'kit bins 6/6' }
      ]
    }
  };

  var demo = document.getElementById('demo');
  if (demo) {
    var img = document.getElementById('demoImg');
    var overlay = document.getElementById('demoOverlay');
    var titleEl = document.getElementById('demoTitle');
    var descEl = document.getElementById('demoDesc');
    var feedEl = document.getElementById('demoFeed');
    var statsEl = document.getElementById('demoStats');
    var camEl = document.getElementById('demoCam');
    var panel = document.getElementById('demoPanel');
    var tabs = Array.prototype.slice.call(demo.querySelectorAll('.demo__tab'));
    var toggle = document.getElementById('demoToggle');
    var armed = true;

    function buildOverlay(mode) {
      var data = DEMOS[mode];
      overlay.innerHTML = '';
      data.dets.forEach(function (d, i) {
        var box = document.createElement('div');
        box.className = 'det det--' + d.cls;
        box.style.left = d.x + '%';
        box.style.top = d.y + '%';
        box.style.width = d.w + '%';
        box.style.height = d.h + '%';
        box.style.transitionDelay = reduced ? '0ms' : (i * 55) + 'ms';

        if (d.label) {
          var label = document.createElement('span');
          label.className = 'det__label';
          label.innerHTML = '<b>' + d.label + '</b>' + (d.tag ? ' <i>' + d.tag + '</i>' : '');
          box.appendChild(label);
        }
        if (typeof d.gauge === 'number') {
          var gauge = document.createElement('div');
          gauge.className = 'gauge';
          gauge.style.top = d.gauge + '%';
          gauge.style.left = d.x + '%';
          gauge.style.width = d.w + '%';
          gauge.style.right = 'auto';
          overlay.appendChild(gauge);
        }
        overlay.appendChild(box);
      });
    }

    function buildFeed(mode) {
      var data = DEMOS[mode];
      feedEl.innerHTML = '';
      data.feed.forEach(function (row) {
        var li = document.createElement('li');
        li.className = 'feed__row';
        li.innerHTML =
          '<span class="feed__t">' + row[0] + '</span>' +
          '<span class="feed__dot' + (row[1] === 'ok' ? '' : ' feed__dot--' + row[1]) + '"></span>' +
          '<span class="feed__txt">' + row[2] + '</span>';
        feedEl.appendChild(li);
      });

      statsEl.innerHTML = '';
      data.stats.forEach(function (pair) {
        var wrap = document.createElement('div');
        wrap.className = 'demo__stat';
        wrap.innerHTML = '<dt>' + pair[0] + '</dt><dd>' + pair[1] + '</dd>';
        statsEl.appendChild(wrap);
      });
    }

    function arm() {
      demo.classList.remove('is-armed');
      if (!armed) return;
      window.setTimeout(function () {
        demo.classList.add('is-armed');
      }, reduced ? 0 : 120);
    }

    function setMode(mode, focusPanel) {
      var data = DEMOS[mode];
      demo.setAttribute('data-mode', mode);

      tabs.forEach(function (t) {
        var on = t.getAttribute('data-mode') === mode;
        t.setAttribute('aria-selected', on ? 'true' : 'false');
        if (on) panel.setAttribute('aria-labelledby', t.id);
      });

      img.style.opacity = '0';
      demo.classList.remove('is-armed');

      window.setTimeout(function () {
        img.src = data.img;
        img.alt = data.alt;
        img.style.opacity = '';
        titleEl.textContent = data.title;
        descEl.textContent = data.desc;
        camEl.textContent = data.cam;
        buildOverlay(mode);
        buildFeed(mode);

        demo.classList.remove('is-scanning');
        void demo.offsetWidth;
        if (!reduced) demo.classList.add('is-scanning');
        arm();
      }, reduced ? 0 : 170);

      if (focusPanel) panel.focus();
    }

    tabs.forEach(function (tab) {
      tab.addEventListener('click', function () {
        setMode(tab.getAttribute('data-mode'), false);
      });
      tab.addEventListener('keydown', function (e) {
        var i = tabs.indexOf(tab);
        var next = null;
        if (e.key === 'ArrowRight') next = tabs[(i + 1) % tabs.length];
        if (e.key === 'ArrowLeft') next = tabs[(i - 1 + tabs.length) % tabs.length];
        if (next) {
          e.preventDefault();
          next.focus();
          setMode(next.getAttribute('data-mode'), false);
        }
      });
    });

    if (toggle) {
      toggle.setAttribute('aria-pressed', 'true');
      toggle.addEventListener('click', function () {
        armed = !armed;
        toggle.setAttribute('aria-pressed', armed ? 'true' : 'false');
        toggle.innerHTML = '<span class="swatch" aria-hidden="true"></span> Detections ' + (armed ? 'on' : 'off');
        if (armed) {
          demo.classList.add('is-armed');
        } else {
          demo.classList.remove('is-armed');
        }
      });
    }

    /* first paint */
    buildOverlay('ppe');
    buildFeed('ppe');
    if (!reduced) {
      window.setTimeout(function () { demo.classList.add('is-scanning'); }, 500);
    }
    arm();
  }

  /* =======================================================================
     Research filters
     ======================================================================= */
  var filterWrap = document.querySelector('.filters');
  if (filterWrap) {
    var filterButtons = Array.prototype.slice.call(filterWrap.querySelectorAll('.filter'));
    var papers = Array.prototype.slice.call(document.querySelectorAll('.paper'));
    var countEl = document.getElementById('paperCount');

    filterButtons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        var cat = btn.getAttribute('data-filter');
        filterButtons.forEach(function (b) {
          b.setAttribute('aria-pressed', b === btn ? 'true' : 'false');
        });
        var shown = 0;
        papers.forEach(function (paper) {
          var match = cat === 'all' || paper.getAttribute('data-cat') === cat;
          paper.hidden = !match;
          if (match) shown += 1;
        });
        if (countEl) {
          countEl.textContent = shown + ' of ' + papers.length + ' papers';
        }
      });
    });
  }

  /* =======================================================================
     AI investment calculator
     ======================================================================= */
  var calcForm = document.getElementById('calcForm');
  if (calcForm) {
    var deployEl = document.getElementById('calcDeploy');
    var runEl = document.getElementById('calcRun');
    var returnEl = document.getElementById('calcReturn');
    var valueEl = document.getElementById('calcValue');
    var textEl = document.getElementById('calcText');
    var metaEl = document.getElementById('calcMeta');
    var barEl = document.getElementById('calcBar');
    var resetEl = document.getElementById('calcReset');

    var usd = function (n) {
      return '$' + Math.round(n).toLocaleString('en-US');
    };

    function update() {
      var deploy = parseFloat(deployEl.value) || 0;
      var run = parseFloat(runEl.value) || 0;
      var ret = parseFloat(returnEl.value) || 0;
      var total = deploy + run;

      if (total <= 0 && ret <= 0) {
        valueEl.textContent = '—';
        valueEl.className = 'verdict__value';
        textEl.textContent = 'Enter three numbers and we will do the subtraction. A negative first year is normal; a system that never repays is not.';
        metaEl.textContent = 'No data leaves this page.';
        barEl.style.width = '0%';
        return;
      }

      var net = ret - total;
      var ratio = total > 0 ? ret / total : 0;
      var positive = net >= 0;

      valueEl.textContent = (positive ? '+' : '−') + usd(Math.abs(net));
      valueEl.className = 'verdict__value ' + (positive ? 'is-good' : 'is-bad');

      if (positive) {
        textEl.innerHTML = 'At these numbers the system repays its first year and returns ' +
          Math.round((ratio - 1) * 100) + '% on top. Keep the maintenance hours in the cost line — that is where these estimates usually flatter themselves.';
      } else {
        textEl.innerHTML = 'Costs exceed returns by ' + usd(Math.abs(net)) +
          ' in year one (' + Math.round((1 - ratio) * 100) + '% short). That can still be the right decision for a safety or compliance reason — just make that argument explicitly rather than pretending the maths works.';
      }

      barEl.style.width = Math.max(3, Math.min(100, (ratio / 2) * 100)) + '%';
      barEl.style.background = positive ? 'var(--olive)' : 'var(--clay)';

      var payback = '';
      if (ret > run && deploy > 0) {
        var months = deploy / ((ret - run) / 12);
        payback = months < 1 ? 'payback under a month' : 'payback ≈ ' + Math.round(months) + ' months';
      } else if (ret > run) {
        payback = 'no upfront cost to recover';
      } else {
        payback = 'does not repay at this run rate';
      }
      metaEl.textContent = 'Year one cost ' + usd(total) + ' · return ' + usd(ret) + ' · ' + payback;
    }

    [deployEl, runEl, returnEl].forEach(function (el) {
      el.addEventListener('input', update);
    });
    resetEl.addEventListener('click', function () {
      deployEl.value = '';
      runEl.value = '';
      returnEl.value = '';
      update();
      deployEl.focus();
    });
    update();
  }
})();
