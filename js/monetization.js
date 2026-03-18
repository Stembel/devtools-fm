/**
 * DevTools.fm Monetization Infrastructure
 * Manages ad slots, support banners, and analytics preparation.
 * Configure ADSENSE_PUB_ID when account is approved.
 */
(function() {
  'use strict';

  // === CONFIGURATION ===
  const CONFIG = {
    adsensePubId: '',  // Set when AdSense is approved: 'ca-pub-XXXXXXXXXX'
    adsenseSlots: {
      toolTop: '',     // Ad slot ID for top of tool page
      toolBottom: '',  // Ad slot ID for bottom of tool page
      sidebar: ''      // Ad slot ID for sidebar
    },
    showSupportBanner: true,
    githubRepo: 'https://github.com/Stembel/devtools-fm'
  };

  // === SUPPORT BANNER ===
  function injectSupportBanner() {
    if (!CONFIG.showSupportBanner) return;

    const footer = document.querySelector('footer');
    if (!footer) return;

    const banner = document.createElement('div');
    banner.className = 'support-banner';
    banner.innerHTML = `
      <div class="container" style="max-width:1200px;margin:0 auto;padding:0 24px;">
        <div style="background:#141416;border:1px solid #2a2a30;border-radius:8px;padding:20px 24px;text-align:center;margin:0 auto;max-width:700px;">
          <p style="color:#e4e4e7;font-size:0.95rem;margin:0 0 12px;font-family:'Inter',sans-serif;">
            <strong>Like DevTools.fm?</strong> Help us keep it free and ad-free.
          </p>
          <div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap;">
            <a href="${CONFIG.githubRepo}" target="_blank" rel="noopener"
               style="display:inline-flex;align-items:center;gap:6px;padding:8px 18px;border-radius:8px;background:#1c1c20;border:1px solid #2a2a30;color:#e4e4e7;font-size:0.85rem;text-decoration:none;font-family:'Inter',sans-serif;transition:border-color 0.2s;"
               onmouseover="this.style.borderColor='#6366f1'" onmouseout="this.style.borderColor='#2a2a30'">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>
              Star on GitHub
            </a>
            <a href="${CONFIG.githubRepo}/issues" target="_blank" rel="noopener"
               style="display:inline-flex;align-items:center;gap:6px;padding:8px 18px;border-radius:8px;background:#6366f1;border:1px solid #6366f1;color:white;font-size:0.85rem;text-decoration:none;font-family:'Inter',sans-serif;transition:background 0.2s;"
               onmouseover="this.style.background='#818cf8'" onmouseout="this.style.background='#6366f1'">
              Suggest a Tool
            </a>
          </div>
        </div>
      </div>
    `;
    banner.style.cssText = 'padding:32px 0 16px;';
    footer.parentNode.insertBefore(banner, footer);
  }

  // === ADSENSE INTEGRATION ===
  function injectAdSense() {
    if (!CONFIG.adsensePubId) return;

    // Load AdSense script
    const script = document.createElement('script');
    script.async = true;
    script.src = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${CONFIG.adsensePubId}`;
    script.crossOrigin = 'anonymous';
    document.head.appendChild(script);

    // Inject ad slot after tool description (tool pages only)
    if (CONFIG.adsenseSlots.toolTop) {
      const desc = document.querySelector('.tool-page .description');
      if (desc) {
        const adDiv = createAdSlot(CONFIG.adsenseSlots.toolTop, 'horizontal');
        desc.parentNode.insertBefore(adDiv, desc.nextSibling);
      }
    }

    // Inject ad slot before footer
    if (CONFIG.adsenseSlots.toolBottom) {
      const footer = document.querySelector('footer');
      if (footer) {
        const adDiv = createAdSlot(CONFIG.adsenseSlots.toolBottom, 'horizontal');
        footer.parentNode.insertBefore(adDiv, footer);
      }
    }
  }

  function createAdSlot(slotId, format) {
    const container = document.createElement('div');
    container.style.cssText = 'text-align:center;padding:16px 0;min-height:90px;max-width:1200px;margin:0 auto;';
    container.innerHTML = `
      <ins class="adsbygoogle"
           style="display:block"
           data-ad-client="${CONFIG.adsensePubId}"
           data-ad-slot="${slotId}"
           data-ad-format="${format === 'horizontal' ? 'auto' : format}"
           data-full-width-responsive="true"></ins>
    `;
    return container;
  }

  // === SIMPLE ANALYTICS (privacy-friendly, no external service) ===
  function trackPageView() {
    // Prepare for future analytics integration
    // Currently just stores in sessionStorage for debugging
    try {
      const views = JSON.parse(sessionStorage.getItem('dtfm_views') || '[]');
      views.push({
        page: location.pathname,
        time: Date.now(),
        ref: document.referrer || 'direct'
      });
      sessionStorage.setItem('dtfm_views', JSON.stringify(views.slice(-50)));
    } catch(e) {}
  }

  // === RELATED TOOLS ===
  function injectRelatedTools() {
    if (!document.querySelector('.tool-page')) return;

    const currentTool = location.pathname.split('/').pop().replace('.html', '');
    const allTools = [
      { id: 'json', name: 'JSON Formatter', icon: '{ }' },
      { id: 'base64', name: 'Base64 Encoder', icon: 'B64' },
      { id: 'hash', name: 'Hash Generator', icon: '#' },
      { id: 'uuid', name: 'UUID Generator', icon: 'ID' },
      { id: 'regex', name: 'Regex Tester', icon: '.*' },
      { id: 'timestamp', name: 'Timestamp Converter', icon: 'T' },
      { id: 'password', name: 'Password Generator', icon: '***' },
      { id: 'qrcode', name: 'QR Code Generator', icon: 'QR' },
      { id: 'color', name: 'Color Converter', icon: 'C' },
      { id: 'sql', name: 'SQL Formatter', icon: 'SQL' },
      { id: 'diff', name: 'Text Diff', icon: '<>' },
      { id: 'wordcount', name: 'Word Counter', icon: 'Wc' },
      { id: 'textcase', name: 'Text Case Converter', icon: 'Aa' },
      { id: 'jwt', name: 'JWT Decoder', icon: 'JWT' },
      { id: 'cron', name: 'Cron Generator', icon: '@' },
      { id: 'markdown', name: 'Markdown Preview', icon: 'MD' },
      { id: 'gradient', name: 'CSS Gradient', icon: 'G' },
      { id: 'palette', name: 'Color Palette', icon: 'P' },
      { id: 'url', name: 'URL Encoder', icon: '%' },
      { id: 'chmod', name: 'Chmod Calculator', icon: '7' },
      { id: 'ipinfo', name: 'IP & Device Info', icon: 'IP' },
      { id: 'html2md', name: 'HTML to Markdown', icon: 'H2M' },
      { id: 'baseconvert', name: 'Base Converter', icon: '0x' },
      { id: 'contrast', name: 'Contrast Checker', icon: 'AA' },
      { id: 'imagecompress', name: 'Image Compressor', icon: 'IMG' },
      { id: 'flexbox', name: 'Flexbox Generator', icon: 'F' },
      { id: 'metatags', name: 'Meta Tag Generator', icon: 'SEO' },
      { id: 'httpstatus', name: 'HTTP Status Codes', icon: 'HTTP' },
    ];

    const others = allTools.filter(t => t.id !== currentTool);
    // Pick 3 random related tools
    const picked = [];
    const copy = [...others];
    for (let i = 0; i < 3 && copy.length; i++) {
      const idx = Math.floor(Math.random() * copy.length);
      picked.push(copy.splice(idx, 1)[0]);
    }

    if (!picked.length) return;

    const footer = document.querySelector('footer');
    if (!footer) return;

    const section = document.createElement('div');
    section.style.cssText = 'max-width:1200px;margin:0 auto;padding:24px 24px 0;';
    section.innerHTML = `
      <p style="color:#8b8b94;font-size:0.8rem;margin-bottom:12px;font-family:'Inter',sans-serif;">More Tools</p>
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px;">
        ${picked.map(t => `
          <a href="${t.id}.html" style="display:flex;align-items:center;gap:8px;padding:10px 16px;background:#141416;border:1px solid #2a2a30;border-radius:8px;color:#e4e4e7;text-decoration:none;font-size:0.85rem;font-family:'Inter',sans-serif;transition:border-color 0.2s;" onmouseover="this.style.borderColor='#6366f1'" onmouseout="this.style.borderColor='#2a2a30'">
            <span style="width:28px;height:28px;background:#1c1c20;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:0.75rem;">${t.icon}</span>
            ${t.name}
          </a>
        `).join('')}
      </div>
    `;
    footer.parentNode.insertBefore(section, footer);
  }

  // === FAVICON ===
  function injectFavicon() {
    // Don't add if already present
    if (document.querySelector('link[rel="icon"]')) return;

    const link = document.createElement('link');
    link.rel = 'icon';
    link.type = 'image/svg+xml';

    // Determine correct relative path based on directory depth
    const path = location.pathname;
    const inSubdir = path.includes('/tools/') || (path.split('/').filter(Boolean).length > 1 && !path.endsWith('/'));
    link.href = inSubdir ? '../favicon.svg' : 'favicon.svg';

    document.head.appendChild(link);
  }

  // === OPEN GRAPH TAGS ===
  function injectOGTags() {
    // Only for tool pages
    if (!document.querySelector('.tool-page')) return;

    // Don't add if OG tags already exist
    if (document.querySelector('meta[property="og:title"]')) return;

    const title = document.title;
    const descMeta = document.querySelector('meta[name="description"]');
    const description = descMeta ? descMeta.getAttribute('content') : '';
    const canonical = document.querySelector('link[rel="canonical"]');
    const url = canonical ? canonical.getAttribute('href') : location.href;

    const ogTags = [
      { property: 'og:title', content: title },
      { property: 'og:description', content: description },
      { property: 'og:type', content: 'website' },
      { property: 'og:url', content: url },
    ];

    const twitterTags = [
      { name: 'twitter:card', content: 'summary' },
      { name: 'twitter:title', content: title },
      { name: 'twitter:description', content: description },
    ];

    ogTags.forEach(function(tag) {
      const meta = document.createElement('meta');
      meta.setAttribute('property', tag.property);
      meta.setAttribute('content', tag.content);
      document.head.appendChild(meta);
    });

    twitterTags.forEach(function(tag) {
      // Don't add if already exists
      if (document.querySelector('meta[name="' + tag.name + '"]')) return;
      const meta = document.createElement('meta');
      meta.setAttribute('name', tag.name);
      meta.setAttribute('content', tag.content);
      document.head.appendChild(meta);
    });
  }

  // === INIT ===
  document.addEventListener('DOMContentLoaded', function() {
    injectFavicon();
    injectOGTags();
    trackPageView();
    injectRelatedTools();
    injectSupportBanner();
    injectAdSense();
  });
})();
