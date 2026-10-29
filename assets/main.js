
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

  var input = document.getElementById('suburb-search-input');
  var results = document.getElementById('suburb-search-results');
  var form = document.getElementById('suburb-search');
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
