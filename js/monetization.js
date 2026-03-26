/**
 * ZeroKit.dev Monetization Infrastructure
 * Manages ad slots, support banners, and analytics preparation.
 * Configure ADSENSE_PUB_ID when account is approved.
 */
(function() {
  'use strict';

  // === CONFIGURATION ===
  const CONFIG = {
    adsensePubId: 'ca-pub-5826340473830405',
    adsenseSlots: {
      toolTop: '',     // Ad slot ID for top of tool page
      toolBottom: '',  // Ad slot ID for bottom of tool page
      sidebar: ''      // Ad slot ID for sidebar
    },
    showSupportBanner: true,
    githubRepo: 'https://github.com/Stembel/zerokit.dev'
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
            <strong>Like ZeroKit.dev?</strong> Help us keep it free and ad-free.
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

  // === RELATED TOOLS (Category-Based for SEO) ===
  function injectRelatedTools() {
    if (!document.querySelector('.tool-page')) return;

    const currentTool = location.pathname.split('/').pop().replace('.html', '');

    // Category-tagged tools for relevant internal linking
    var cats = {
      json: ['json','jsonpath','jsondiff','jsontree','jsonschema','json2yaml','json-csv','json2ts','json2schema'],
      encode: ['base64','base58','url','htmlentity','escape','dataurl','textbinary','imagebase64'],
      hash: ['hash','hmac','sshkeygen','password','uuid'],
      css: ['flexbox','cssgrid','gradient','boxshadow','borderradius','textshadow','cssanimation','clippath','cssfilter','tailwind','cssunits'],
      color: ['color','colorpicker','palette','contrast','colorblind','htmlcolors'],
      text: ['wordcount','textcase','diff','regex','lorem','asciiart','emoji','markdown','fontpreview'],
      convert: ['html2md','baseconvert','timestamp','toml','sql2mongo','ipconvert','curl2code'],
      network: ['dns-lookup','ssl-checker','http-headers','whois','redirect-checker','status-checker','email-validate','tech-detect','ipinfo','subnet','subnetvisual','apitester'],
      devops: ['cron','crontab','dockercompose','nginx','htaccess','robots','manifest','envfile','chmod','gitcheat','sshkeygen'],
      reference: ['httpstatus','httpmethods','regexref','sqlref','shortcuts','htmlcolors','cssunits'],
      format: ['json','sql','htmlformat','markdown','minifier','svgoptimizer','csvviewer'],
      seo: ['metatags','ogpreview','favicon','githubprofile','robots'],
      jwt: ['jwt','jwtbuilder'],
      image: ['imagecompress','svgoptimizer','placeholder','favicon','qrcode','imagebase64','aspectratio']
    };

    // Find which categories the current tool belongs to
    var myCats = [];
    for (var cat in cats) {
      if (cats[cat].indexOf(currentTool) !== -1) myCats.push(cat);
    }

    // Collect related tools from same categories (deduplicated)
    var related = {};
    myCats.forEach(function(cat) {
      cats[cat].forEach(function(tid) {
        if (tid !== currentTool) related[tid] = true;
      });
    });

    // Tool display info
    var toolInfo = {
      'json': {n:'JSON Formatter',i:'{ }'},'base64': {n:'Base64 Encoder',i:'B64'},'hash': {n:'Hash Generator',i:'#'},
      'uuid': {n:'UUID Generator',i:'ID'},'regex': {n:'Regex Tester',i:'.*'},'timestamp': {n:'Timestamp',i:'T'},
      'password': {n:'Password Gen',i:'***'},'qrcode': {n:'QR Code',i:'QR'},'color': {n:'Color Converter',i:'C'},
      'sql': {n:'SQL Formatter',i:'SQL'},'diff': {n:'Text Diff',i:'<>'},'wordcount': {n:'Word Counter',i:'Wc'},
      'textcase': {n:'Text Case',i:'Aa'},'jwt': {n:'JWT Decoder',i:'JWT'},'cron': {n:'Cron Generator',i:'@'},
      'markdown': {n:'Markdown Preview',i:'MD'},'gradient': {n:'CSS Gradient',i:'G'},'palette': {n:'Color Palette',i:'P'},
      'url': {n:'URL Encoder',i:'%'},'chmod': {n:'Chmod Calculator',i:'7'},'ipinfo': {n:'IP & Device Info',i:'IP'},
      'html2md': {n:'HTML to Markdown',i:'H2M'},'baseconvert': {n:'Base Converter',i:'0x'},
      'contrast': {n:'Contrast Checker',i:'AA'},'imagecompress': {n:'Image Compressor',i:'IMG'},
      'flexbox': {n:'Flexbox Generator',i:'F'},'metatags': {n:'Meta Tag Gen',i:'SEO'},
      'httpstatus': {n:'HTTP Status Codes',i:'HTTP'},'dns-lookup': {n:'DNS Lookup',i:'DNS'},
      'ssl-checker': {n:'SSL Checker',i:'SSL'},'http-headers': {n:'HTTP Headers',i:'HDR'},
      'whois': {n:'WHOIS Lookup',i:'WH'},'redirect-checker': {n:'Redirect Checker',i:'3xx'},
      'subnet': {n:'Subnet Calculator',i:'IP4'},'apitester': {n:'API Tester',i:'API'},
      'status-checker': {n:'Status Checker',i:'UP?'},'email-validate': {n:'Email Validator',i:'@'},
      'tech-detect': {n:'Tech Detector',i:'TEC'},'jsonschema': {n:'JSON Schema',i:'JS'},
      'robots': {n:'Robots.txt Gen',i:'BOT'},'jsonpath': {n:'JSONPath',i:'$.'},
      'mdtable': {n:'MD Table Gen',i:'MD'},'cssgrid': {n:'CSS Grid',i:'GR'},
      'favicon': {n:'Favicon Gen',i:'FV'},'htaccess': {n:'.htaccess Gen',i:'.ht'},
      'borderradius': {n:'Border Radius',i:'BR'},'placeholder': {n:'Placeholder Image',i:'PH'},
      'aspectratio': {n:'Aspect Ratio',i:'16:9'},'ogpreview': {n:'OG Preview',i:'OG'},
      'textbinary': {n:'Text to Binary',i:'01'},'svgoptimizer': {n:'SVG Optimizer',i:'SVG'},
      'cssanimation': {n:'CSS Animation',i:'AN'},'jwtbuilder': {n:'JWT Builder',i:'JW+'},
      'toml': {n:'TOML Converter',i:'TML'},'crontab': {n:'Crontab Tester',i:'CT'},
      'csvviewer': {n:'CSV Viewer',i:'CSV'},'colorblind': {n:'Color Blindness',i:'CB'},
      'nginx': {n:'Nginx Config',i:'NGX'},'dockercompose': {n:'Docker Compose',i:'DC'},
      'json2ts': {n:'JSON to TypeScript',i:'TS'},'envfile': {n:'.env Editor',i:'.env'},
      'gitcheat': {n:'Git Cheatsheet',i:'GIT'},'htmlformat': {n:'HTML Formatter',i:'HTM'},
      'asciiart': {n:'ASCII Art',i:'A#'},'cssunits': {n:'CSS Units',i:'px'},
      'sql2mongo': {n:'SQL to MongoDB',i:'MDB'},'tailwind': {n:'Tailwind Lookup',i:'TW'},
      'jsondiff': {n:'JSON Diff',i:'J<>'},'sshkeygen': {n:'SSH Key Gen',i:'SSH'},
      'json2yaml': {n:'JSON to YAML',i:'YML'},'base58': {n:'Base58 Encoder',i:'B58'},
      'colorpicker': {n:'Color Picker',i:'CP'},'regexref': {n:'Regex Reference',i:'RX'},
      'clippath': {n:'CSS Clip-Path',i:'CP'},'githubprofile': {n:'GitHub README',i:'GH'},
      'jsontree': {n:'JSON Tree',i:'JT'},'textshadow': {n:'Text Shadow',i:'TS'},
      'ipconvert': {n:'IP Converter',i:'IPC'},'shortcuts': {n:'Shortcuts',i:'KB'},
      'curl2code': {n:'cURL to Code',i:'cU'},'htmlcolors': {n:'HTML Colors',i:'HC'},
      'dataurl': {n:'Data URL',i:'DU'},'hmac': {n:'HMAC Generator',i:'HM'},
      'sqlref': {n:'SQL Reference',i:'SQ'},'cssfilter': {n:'CSS Filter',i:'FI'},
      'fontpreview': {n:'Font Preview',i:'FP'},'httpmethods': {n:'HTTP Methods',i:'GET'},
      'json2schema': {n:'JSON Schema Gen',i:'JSG'},'manifest': {n:'PWA Manifest',i:'PWA'},
      'semver': {n:'SemVer Check',i:'SV'},'subnetvisual': {n:'Subnet Visual',i:'SN'},
      'emoji': {n:'Emoji Picker',i:'EM'},'json-csv': {n:'JSON to CSV',i:'CSV'},
      'imagebase64': {n:'Image to Base64',i:'I64'},'lorem': {n:'Lorem Ipsum',i:'Li'},
      'minifier': {n:'CSS/JS Minifier',i:'Min'},'htmlentity': {n:'HTML Entity',i:'&'},
      'escape': {n:'String Escape',i:'\\'},'boxshadow': {n:'Box Shadow',i:'SH'}
    };

    // Pick up to 5 from related, shuffle
    var relatedIds = Object.keys(related);
    for (var i = relatedIds.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = relatedIds[i]; relatedIds[i] = relatedIds[j]; relatedIds[j] = tmp;
    }
    var picked = relatedIds.slice(0, 5).map(function(id) {
      var info = toolInfo[id];
      return info ? { id: id, name: info.n, icon: info.i } : null;
    }).filter(Boolean);

    if (!picked.length) return;

    const footer = document.querySelector('footer');
    if (!footer) return;

    const section = document.createElement('div');
    section.style.cssText = 'max-width:1200px;margin:0 auto;padding:24px 24px 0;';
    section.innerHTML = `
      <p style="color:#8b8b94;font-size:0.8rem;margin-bottom:12px;font-family:'Inter',sans-serif;">Related Tools</p>
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

  // === AFFILIATE / RESOURCE LINKS ===
  const RESOURCES = [
    { name: 'DigitalOcean', desc: '$200 free credits for new users', url: 'https://www.digitalocean.com/', category: 'hosting', icon: 'DO' },
    { name: 'Namecheap', desc: 'Domains from $1.98/yr', url: 'https://www.namecheap.com/', category: 'domains', icon: 'NC' },
    { name: 'Cloudflare', desc: 'Free CDN, DNS & DDoS protection', url: 'https://www.cloudflare.com/', category: 'hosting', icon: 'CF' },
    { name: 'Vercel', desc: 'Deploy frontend apps instantly', url: 'https://vercel.com/', category: 'hosting', icon: 'V' },
    { name: 'GitHub Pro', desc: 'Advanced tools for developers', url: 'https://github.com/pricing', category: 'tools', icon: 'GH' },
    { name: 'Udemy Dev Courses', desc: 'Learn new skills from $9.99', url: 'https://www.udemy.com/courses/development/', category: 'learning', icon: 'U' },
  ];

  function injectResourceLinks() {
    // Only on homepage
    if (document.querySelector('.tool-page')) return;
    const footer = document.querySelector('footer');
    if (!footer) return;

    const section = document.createElement('div');
    section.style.cssText = 'max-width:1200px;margin:0 auto;padding:40px 24px 0;';
    section.innerHTML = `
      <h2 style="font-size:1.1rem;font-weight:700;color:var(--text);margin-bottom:16px;font-family:'Inter',sans-serif;">Recommended for Developers</h2>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px;margin-bottom:24px;">
        ${RESOURCES.map(r => `
          <a href="${r.url}" target="_blank" rel="noopener sponsored"
             style="display:flex;align-items:center;gap:12px;padding:14px 16px;background:#141416;border:1px solid #2a2a30;border-radius:8px;color:#e4e4e7;text-decoration:none;transition:border-color 0.2s;"
             onmouseover="this.style.borderColor='#6366f1'" onmouseout="this.style.borderColor='#2a2a30'">
            <span style="min-width:36px;height:36px;background:#1c1c20;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:0.7rem;font-weight:700;color:#6366f1;">${r.icon}</span>
            <span>
              <strong style="display:block;font-size:0.9rem;">${r.name}</strong>
              <span style="font-size:0.8rem;color:#8b8b94;">${r.desc}</span>
            </span>
          </a>
        `).join('')}
      </div>
    `;
    footer.parentNode.insertBefore(section, footer);
  }

  // === SPONSORSHIP CTA ===
  function injectSponsorCTA() {
    // Only on homepage
    if (document.querySelector('.tool-page')) return;
    const footer = document.querySelector('footer');
    if (!footer) return;

    const cta = document.createElement('div');
    cta.style.cssText = 'max-width:700px;margin:0 auto;padding:32px 24px 0;text-align:center;';
    cta.innerHTML = `
      <div style="background:linear-gradient(135deg,#141416 0%,#1a1a2e 100%);border:1px solid #2a2a30;border-radius:12px;padding:32px 24px;">
        <h3 style="font-size:1.1rem;font-weight:700;color:#e4e4e7;margin-bottom:8px;font-family:'Inter',sans-serif;">Sponsor ZeroKit.dev</h3>
        <p style="color:#8b8b94;font-size:0.9rem;margin-bottom:20px;font-family:'Inter',sans-serif;">
          Reach 1000s of developers. Your brand on every tool page.
        </p>
        <a href="mailto:hello@zerokit.dev?subject=ZeroKit.dev%20Sponsorship&body=Hi%2C%20I%27m%20interested%20in%20sponsoring%20ZeroKit.dev."
           style="display:inline-flex;align-items:center;gap:8px;padding:10px 24px;border-radius:8px;background:#6366f1;border:1px solid #6366f1;color:white;font-size:0.9rem;text-decoration:none;font-family:'Inter',sans-serif;transition:background 0.2s;"
           onmouseover="this.style.background='#818cf8'" onmouseout="this.style.background='#6366f1'">
          Get in Touch
        </a>
      </div>
    `;
    footer.parentNode.insertBefore(cta, footer);
  }

  // === JSON-LD STRUCTURED DATA ===
  function injectStructuredData() {
    // Tool pages: WebApplication schema
    if (document.querySelector('.tool-page')) {
      const title = document.title.replace(' - ZeroKit.dev', '');
      const descMeta = document.querySelector('meta[name="description"]');
      const description = descMeta ? descMeta.getAttribute('content') : '';
      const canonical = document.querySelector('link[rel="canonical"]');
      const url = canonical ? canonical.getAttribute('href') : location.href;

      const schema = {
        '@context': 'https://schema.org',
        '@type': 'WebApplication',
        'name': title,
        'description': description,
        'url': url,
        'applicationCategory': 'DeveloperApplication',
        'operatingSystem': 'Any',
        'browserRequirements': 'Requires JavaScript',
        'offers': {
          '@type': 'Offer',
          'price': '0',
          'priceCurrency': 'USD'
        },
        'author': {
          '@type': 'Organization',
          'name': 'ZeroKit.dev',
          'url': 'https://zerokit.dev/'
        }
      };

      const script = document.createElement('script');
      script.type = 'application/ld+json';
      script.textContent = JSON.stringify(schema);
      document.head.appendChild(script);
      return;
    }

    // Homepage: WebSite + ItemList schema
    const homepageSchema = [
      {
        '@context': 'https://schema.org',
        '@type': 'WebSite',
        'name': 'ZeroKit.dev',
        'url': 'https://zerokit.dev/',
        'description': 'Free online developer tools. 100+ tools including JSON formatter, Base64 encoder, hash generator, regex tester, DNS lookup, and more.',
        'potentialAction': {
          '@type': 'SearchAction',
          'target': 'https://zerokit.dev/?q={search_term_string}',
          'query-input': 'required name=search_term_string'
        }
      },
      {
        '@context': 'https://schema.org',
        '@type': 'ItemList',
        'name': 'Developer Tools',
        'numberOfItems': 100,
        'itemListElement': Array.from(document.querySelectorAll('.tool-card')).slice(0, 10).map(function(card, i) {
          const link = card.querySelector('a') || card;
          const name = card.querySelector('h3, .tool-name');
          return {
            '@type': 'ListItem',
            'position': i + 1,
            'url': link.href || '',
            'name': name ? name.textContent.trim() : ''
          };
        })
      }
    ];

    homepageSchema.forEach(function(schema) {
      const script = document.createElement('script');
      script.type = 'application/ld+json';
      script.textContent = JSON.stringify(schema);
      document.head.appendChild(script);
    });
  }

  // === FAQ SCHEMA FOR RICH SNIPPETS ===
  function injectFAQSchema() {
    if (!document.querySelector('.tool-page')) return;

    var toolId = location.pathname.split('/').pop().replace('.html', '');
    var faqs = {
      'json': [
        {q:'What is a JSON formatter?', a:'A JSON formatter takes raw or minified JSON data and reformats it with proper indentation and line breaks, making it easier to read and debug.'},
        {q:'Is my data safe when using this JSON formatter?', a:'Yes. This tool runs entirely in your browser. Your JSON data is never sent to any server.'},
        {q:'Can I validate JSON online?', a:'Yes. This tool automatically validates your JSON and shows syntax errors with line numbers.'}
      ],
      'base64': [
        {q:'What is Base64 encoding?', a:'Base64 is a binary-to-text encoding scheme that represents binary data as ASCII text. It is commonly used in email, URLs, and data URIs.'},
        {q:'Is Base64 encryption?', a:'No. Base64 is encoding, not encryption. It does not provide security — anyone can decode Base64 data.'},
        {q:'When should I use Base64?', a:'Use Base64 when you need to embed binary data (images, files) in text-based formats like HTML, CSS, JSON, or email.'}
      ],
      'hash': [
        {q:'What is a hash function?', a:'A hash function takes input data and produces a fixed-size string of characters (the hash). Common algorithms include MD5, SHA-1, SHA-256, and SHA-512.'},
        {q:'Are hashes reversible?', a:'No. Cryptographic hash functions are one-way — you cannot reverse a hash to get the original input.'},
        {q:'Which hash algorithm should I use?', a:'Use SHA-256 or SHA-512 for security purposes. MD5 and SHA-1 are considered weak and should only be used for checksums, not security.'}
      ],
      'regex': [
        {q:'What is regex?', a:'Regex (regular expressions) is a pattern-matching language used to search, match, and manipulate text. It is supported in virtually all programming languages.'},
        {q:'How do I test a regular expression?', a:'Paste your regex pattern and test string into this tool. It highlights matches in real-time and shows capture groups.'},
        {q:'What does the g flag mean in regex?', a:'The g (global) flag finds all matches in the string, not just the first one.'}
      ],
      'jwt': [
        {q:'What is a JWT token?', a:'JWT (JSON Web Token) is a compact, URL-safe token format used for authentication and information exchange. It contains a header, payload, and signature.'},
        {q:'Can you decode a JWT without the secret?', a:'Yes. The header and payload of a JWT are Base64-encoded (not encrypted). Only the signature requires the secret key to verify.'},
        {q:'Are JWT tokens secure?', a:'JWTs are secure when properly implemented — use strong secrets, short expiration times, and HTTPS.'}
      ],
      'dns-lookup': [
        {q:'What is DNS lookup?', a:'DNS lookup queries Domain Name System servers to find the IP address and other records (MX, AAAA, PTR) associated with a domain name.'},
        {q:'What are MX records?', a:'MX (Mail Exchanger) records specify which mail servers handle email for a domain.'},
        {q:'Why does DNS lookup matter?', a:'DNS lookups help debug email delivery issues, verify domain configuration, and troubleshoot website connectivity problems.'}
      ],
      'ssl-checker': [
        {q:'How do I check if an SSL certificate is valid?', a:'Enter the domain name in this tool. It checks the certificate chain, expiry date, issuer, and cipher strength.'},
        {q:'What happens when an SSL certificate expires?', a:'Browsers show security warnings, users lose trust, and search engines may penalize the site ranking.'},
        {q:'Is SSL the same as TLS?', a:'SSL (Secure Sockets Layer) is the predecessor of TLS (Transport Layer Security). Modern HTTPS uses TLS, but the term SSL is still commonly used.'}
      ],
      'color': [
        {q:'How do I convert HEX to RGB?', a:'Enter a HEX color code (e.g., #6366f1) and this tool instantly converts it to RGB, HSL, and other formats.'},
        {q:'What is the difference between HEX and RGB?', a:'HEX uses hexadecimal notation (#RRGGBB), while RGB uses decimal values (0-255) for red, green, and blue channels. They represent the same colors.'}
      ],
      'flexbox': [
        {q:'What is CSS Flexbox?', a:'Flexbox is a CSS layout module that provides an efficient way to align, distribute, and space items within a container, even when their sizes are unknown.'},
        {q:'When should I use Flexbox vs Grid?', a:'Use Flexbox for one-dimensional layouts (row OR column). Use CSS Grid for two-dimensional layouts (rows AND columns simultaneously).'}
      ],
      'password': [
        {q:'How long should a password be?', a:'At least 12-16 characters. Longer passwords are exponentially harder to crack. Use a mix of uppercase, lowercase, numbers, and special characters.'},
        {q:'Is this password generator safe?', a:'Yes. Passwords are generated entirely in your browser using the Web Crypto API. No passwords are ever sent to a server.'}
      ],
      'qrcode': [
        {q:'What is a QR code?', a:'A QR (Quick Response) code is a 2D barcode that can store URLs, text, contact info, and other data. It can be scanned by smartphone cameras.'},
        {q:'Can I generate a QR code for free?', a:'Yes. This tool generates QR codes instantly in your browser for any text or URL, completely free.'}
      ]
    };

    var toolFaqs = faqs[toolId];
    if (!toolFaqs) return;

    var faqSchema = {
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      'mainEntity': toolFaqs.map(function(faq) {
        return {
          '@type': 'Question',
          'name': faq.q,
          'acceptedAnswer': {
            '@type': 'Answer',
            'text': faq.a
          }
        };
      })
    };

    var script = document.createElement('script');
    script.type = 'application/ld+json';
    script.textContent = JSON.stringify(faqSchema);
    document.head.appendChild(script);
  }

  // === AADS CRYPTO ADS ===
  function injectAADS() {
    var footer = document.querySelector('footer');
    if (!footer) return;

    // Bottom ad (before footer) - all pages
    var adContainer = document.createElement('div');
    adContainer.style.cssText = 'max-width:1200px;margin:0 auto;padding:16px 24px;text-align:center;';
    adContainer.innerHTML = '<div style="width:100%;margin:auto;position:relative;z-index:1;"><iframe data-aa="2431745" src="//acceptable.a-ads.com/2431745/?size=Adaptive" style="border:0;padding:0;width:70%;height:auto;overflow:hidden;display:block;margin:auto"></iframe></div>';
    footer.parentNode.insertBefore(adContainer, footer);

    // Top ad (after tool description) - tool pages only
    if (document.querySelector('.tool-page')) {
      var desc = document.querySelector('.tool-page .description, .tool-page p:first-of-type');
      if (desc) {
        var topAd = document.createElement('div');
        topAd.style.cssText = 'max-width:1200px;margin:16px auto;padding:8px 24px;text-align:center;';
        topAd.innerHTML = '<div style="width:100%;margin:auto;"><iframe data-aa="2431745" src="//acceptable.a-ads.com/2431745/?size=728x90" style="border:0;padding:0;width:728px;max-width:100%;height:90px;overflow:hidden;display:block;margin:auto"></iframe></div>';
        desc.parentNode.insertBefore(topAd, desc.nextSibling);
      }
    }
  }

  // === INIT ===
  document.addEventListener('DOMContentLoaded', function() {
    injectFavicon();
    injectOGTags();
    injectStructuredData();
    injectFAQSchema();
    trackPageView();
    injectRelatedTools();
    injectResourceLinks();
    injectSponsorCTA();
    injectSupportBanner();
    injectAdSense();
    injectAADS();
  });
})();
