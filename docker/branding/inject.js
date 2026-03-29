// Cortellis CLI — Login page banner injection
(function() {
  // Hide the logo image (replaced by ASCII banner)
  var style = document.createElement('style');
  style.textContent = 'img[src*="logo"]{display:none!important}';
  document.head.appendChild(style);

  const BANNER = `
  ██████╗ ██████╗ ██████╗ ████████╗███████╗██╗     ██╗     ██╗███████╗
 ██╔════╝██╔═══██╗██╔══██╗╚══██╔══╝██╔════╝██║     ██║     ██║██╔════╝
 ██║     ██║   ██║██████╔╝   ██║   █████╗  ██║     ██║     ██║███████╗
 ██║     ██║   ██║██╔══██╗   ██║   ██╔══╝  ██║     ██║     ██║╚════██║
 ╚██████╗╚██████╔╝██║  ██║   ██║   ███████╗███████╗███████╗██║███████║
  ╚═════╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚══════╝╚══════╝╚══════╝╚═╝╚══════╝`;

  function injectBanner() {
    // Don't inject if already there
    if (document.getElementById('cortellis-banner')) return;

    // Find the login form container
    const root = document.getElementById('root');
    if (!root || !root.children.length) return;

    // Look for the form or a heading with "Welcome" or "Sign in"
    const headings = root.querySelectorAll('h1, h2, h3, [class*="title"], [class*="heading"]');
    let target = null;
    for (const h of headings) {
      if (h.textContent.includes('Cortellis') || h.textContent.includes('Welcome') || h.textContent.includes('Sign in')) {
        target = h;
        break;
      }
    }

    if (!target) {
      // Fallback: prepend to first card/container
      target = root.querySelector('[class*="card"], [class*="container"], [class*="form"], [class*="auth"]');
    }

    if (target && target.parentNode) {
      const banner = document.createElement('pre');
      banner.id = 'cortellis-banner';
      banner.textContent = BANNER;
      banner.style.cssText = 'text-align:center;color:#1a365d;font-size:8px;line-height:1.1;font-family:monospace;margin:0 auto 16px;padding:16px 0 0;user-select:none;overflow:hidden;white-space:pre;';
      target.parentNode.insertBefore(banner, target);

      // Add subtitle
      const sub = document.createElement('div');
      sub.style.cssText = 'text-align:center;color:#4a5568;font-size:12px;letter-spacing:4px;margin-bottom:16px;font-family:sans-serif;';
      sub.textContent = 'PHARMACEUTICAL INTELLIGENCE';
      target.parentNode.insertBefore(sub, target);
    }
  }

  // Observe DOM changes (React renders after page load)
  const observer = new MutationObserver(function() {
    injectBanner();
  });

  if (document.getElementById('root')) {
    observer.observe(document.getElementById('root'), { childList: true, subtree: true });
  }

  // Also try on load
  window.addEventListener('load', function() {
    setTimeout(injectBanner, 500);
    setTimeout(injectBanner, 1500);
  });
})();
