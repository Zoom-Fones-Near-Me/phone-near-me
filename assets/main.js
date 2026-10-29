
(function(){
  var toggle = document.querySelector('.nav-toggle');
  var links = document.getElementById('nav-links');
  if (toggle && links) toggle.addEventListener('click', function(){
    var open = links.classList.toggle('open');
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  });

  function fmtH(h){ return (h > 12 ? h - 12 : h) + (h >= 12 ? 'pm' : 'am'); }
  function sydneyNow(){ return new Date(new Date().toLocaleString('en-US', { timeZone: 'Australia/Sydney' })); }
  document.querySelectorAll('.js-status').forEach(function(el){
    var hoursAttr = el.getAttribute('data-hours');
    var hours = hoursAttr ? JSON.parse(hoursAttr) : null;
    var staticText = el.textContent;
    if (!hours) {
      var opens = el.getAttribute('data-opens');
      if (opens && new Date() < new Date(opens)) { el.textContent = 'Coming soon \u00b7 ' + staticText; return; }
      el.textContent = 'Open now'; el.style.color = '#1d8a3a'; return;
    }
    var now = sydneyNow(), d = now.getDay(), t = now.getHours() + now.getMinutes() / 60;
    var slot = hours[d], open = t >= slot[0] && t < slot[1];
    if (open) { el.textContent = 'Open now \u00b7 until ' + fmtH(slot[1]) + ' \u00b7 ' + staticText; el.style.color = '#1d8a3a'; }
    else {
      var label = t < slot[0] ? ('Closed \u00b7 opens ' + fmtH(slot[0]) + ' today') : ('Closed \u00b7 opens ' + fmtH(hours[(d + 1) % 7][0]) + ' tomorrow');
      el.textContent = label + ' \u00b7 ' + staticText;
    }
  });

  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function(entries){
      entries.forEach(function(entry){
        if (entry.isIntersecting) {
          entry.target.style.opacity = '1';
          entry.target.style.transform = 'none';
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });
    document.querySelectorAll('[data-reveal]').forEach(function(el){
      var r = el.getBoundingClientRect();
      if (r.top < window.innerHeight) return;
      el.style.opacity = '0';
      el.style.transform = 'translateY(28px)';
      el.style.transition = 'opacity .9s cubic-bezier(.2,.8,.2,1), transform .9s cubic-bezier(.2,.8,.2,1)';
      io.observe(el);
    });
  }

  var mapEl = document.getElementById('leaflet-map');
  if (mapEl && window.L) {
    try {
      var suburbPt = JSON.parse(mapEl.getAttribute('data-suburb'));
      var shopPts = JSON.parse(mapEl.getAttribute('data-shops'));
      var map = L.map(mapEl, { scrollWheelZoom: false }).setView(suburbPt.ll, 12);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
      }).addTo(map);
      var bounds = [suburbPt.ll];
      L.marker(suburbPt.ll).addTo(map).bindPopup(suburbPt.name).openPopup();
      shopPts.forEach(function(s){
        bounds.push(s.ll);
        L.marker(s.ll).addTo(map).bindPopup('<strong>' + s.name + '</strong><br><a href="' + s.maps + '" target="_blank" rel="noopener">Directions</a>');
      });
      map.fitBounds(bounds, { padding: [28, 28] });
    } catch (e) { /* leave the aside empty if the map fails to init */ }
  }

  var input = document.getElementById('suburb-search-input');
  var results = document.getElementById('suburb-search-results');
  var form = document.getElementById('search');
  if (!input || !results || !form) return;
  var DATA = null;
  fetch('/assets/suburbs.json').then(function(r){ return r.json(); }).then(function(j){ DATA = j; });
  var current = [];
  input.addEventListener('input', function(){
    var q = input.value.trim().toLowerCase();
    results.hidden = true;
    current = [];
    if (!q || !DATA) return;
    var scored = DATA.map(function(s){
      var n = s.n.toLowerCase();
      var score = s.p.indexOf(q) === 0 ? 0 : n.indexOf(q) === 0 ? 1 : n.indexOf(' ' + q) !== -1 ? 2 : n.indexOf(q) !== -1 ? 3 : 9;
      return { s: s, score: score };
    }).filter(function(x){ return x.score < 9; }).sort(function(a, b){ return a.score - b.score || a.s.n.localeCompare(b.s.n); }).slice(0, 6);
    current = scored.map(function(x){ return x.s; });
    if (!current.length) return;
    results.innerHTML = current.map(function(s){ return '<a href="/' + s.s + '/">' + s.n + '<span class="muted">' + s.r + '</span></a>'; }).join('');
    results.hidden = false;
  });
  form.addEventListener('submit', function(e){
    e.preventDefault();
    if (current.length) window.location.href = '/' + current[0].s + '/';
  });
  document.addEventListener('click', function(e){ if (!form.contains(e.target)) results.hidden = true; });
})();
