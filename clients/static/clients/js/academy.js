/**
 * Mortacc Academy — Interactive Learning Experience
 * Vanilla JS. No frameworks required.
 */
(function() {
  'use strict';

  // ── Intersection Observer for scroll animations ──────────────────
  var animatedElements = document.querySelectorAll(
    '.flowchart-step, .timeline-event, .comparison-row, .chapter-timeline-item'
  );

  if (animatedElements.length && 'IntersectionObserver' in window) {
    var observer = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (entry.isIntersecting) {
          entry.target.style.opacity = '1';
          entry.target.style.transform = 'translateY(0)';
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.15, rootMargin: '0px 0px -30px 0px' });

    animatedElements.forEach(function(el) {
      observer.observe(el);
    });
  }

  // ── Progress bar scroll tracking ─────────────────────────────────
  var progressFill = document.querySelector('.player-progress-fill');
  var playerContent = document.getElementById('playerContent');

  if (progressFill && playerContent) {
    window.addEventListener('scroll', function() {
      var contentRect = playerContent.getBoundingClientRect();
      var totalHeight = playerContent.scrollHeight - window.innerHeight;
      if (totalHeight <= 0) { progressFill.style.width = '100%'; return; }

      var scrolled = -contentRect.top;
      var percent = Math.min(100, Math.max(0, (scrolled / totalHeight) * 100));
      progressFill.style.width = percent + '%';
    }, { passive: true });
  }

  // ── FAQ Accordion ────────────────────────────────────────────────
  var faqItems = document.querySelectorAll('.faq-item');
  faqItems.forEach(function(item) {
    item.addEventListener('click', function() {
      item.classList.toggle('open');
    });
  });

  // ── Module card hover entrance animations ────────────────────────
  if ('IntersectionObserver' in window) {
    var cardObserver = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (entry.isIntersecting) {
          entry.target.style.opacity = '1';
          entry.target.style.transform = 'translateY(0)';
          cardObserver.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });

    document.querySelectorAll('.module-card').forEach(function(card, i) {
      card.style.opacity = '0';
      card.style.transform = 'translateY(16px)';
      card.style.transition = 'opacity .5s ease, transform .5s ease';
      card.style.transitionDelay = (i % 6) * .06 + 's';
      cardObserver.observe(card);
    });
  }

})();
