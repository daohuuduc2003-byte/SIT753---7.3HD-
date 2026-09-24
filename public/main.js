/* ── 1. Dynamic greeting banner ──────────────────────────── */
(function () {
  var banner = document.getElementById('greeting-banner');
  if (!banner) return;
 
  var hour = new Date().getHours();
  var greeting;
 
  if (hour >= 5 && hour < 12) {
    greeting = '🌄 Good morning, explorer! Perfect conditions for a morning hike today.';
  } else if (hour >= 12 && hour < 17) {
    greeting = '☀️ Good afternoon! Check out our latest trail routes below.';
  } else if (hour >= 17 && hour < 21) {
    greeting = '🌆 Good evening! Planning your next adventure? We have just the trail for you.';
  } else {
    greeting = '🌙 Night owl? Great trails await you tomorrow – browse at your own pace.';
  }
 
  banner.textContent = greeting;
})();
 
/* ── 2. Mobile navbar toggle ─────────────────────────────── */
(function () {
  var toggle = document.getElementById('navToggle');
  var menu   = document.getElementById('navMenu');
  if (!toggle || !menu) return;
 
  // On mobile, hide the menu initially
  function applyMobileStyles() {
    if (window.innerWidth <= 767) {
      menu.style.display = 'none';
      menu.style.width   = '100%';
      menu.style.flexDirection = 'column';
    } else {
      menu.style.display = 'flex';
      menu.style.width   = '';
      menu.style.flexDirection = '';
    }
  }
 
  applyMobileStyles();
  window.addEventListener('resize', applyMobileStyles);
 
  toggle.addEventListener('click', function () {
    var isVisible = menu.style.display === 'flex';
    menu.style.display    = isVisible ? 'none' : 'flex';
    toggle.setAttribute('aria-expanded', String(!isVisible));
  });
})();
 
 
/* ── 3. Back-to-top button ───────────────────────────────── */
(function () {
  var btn = document.getElementById('back-to-top');
  if (!btn) return;
 
  window.addEventListener('scroll', function () {
    btn.classList.toggle('visible', window.scrollY > 400);
  });
 
  btn.addEventListener('click', function () {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
})();
 
 
/* ── 4. Scroll-reveal animation ──────────────────────────── */
(function () {
  var els = document.querySelectorAll('.reveal');
  if (!els.length) return;
 
  if ('IntersectionObserver' in window) {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });
 
    els.forEach(function (el) { observer.observe(el); });
  } else {
    // Fallback: show all immediately for older browsers
    els.forEach(function (el) { el.classList.add('visible'); });
  }
})();
 
/* ── 5. Highlight active nav link from URL ───────────────── */
(function () {
  var page  = window.location.pathname.split('/').pop() || 'index.html';
  var links = document.querySelectorAll('.navbar-nav .nav-link');
  links.forEach(function (link) {
    var href = link.getAttribute('href');
    if (href === page) {
      link.classList.add('active');
      link.setAttribute('aria-current', 'page');
    }
  });
})();