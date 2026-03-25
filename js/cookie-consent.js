/**
 * GDPR Cookie Consent Banner
 * Blocks AdSense until user consents to cookies.
 * Required for EU/DSGVO compliance.
 */
(function() {
  'use strict';

  var CONSENT_KEY = 'zerokit_cookie_consent';

  function hasConsent() {
    try { return localStorage.getItem(CONSENT_KEY) === 'accepted'; }
    catch(e) { return false; }
  }

  function setConsent(value) {
    try { localStorage.setItem(CONSENT_KEY, value); }
    catch(e) {}
  }

  function loadAdSense() {
    // AdSense script tags are already in HTML but won't show ads without consent signal
    // Google's consent mode: signal that consent was given
    window.dataLayer = window.dataLayer || [];
    function gtag(){ dataLayer.push(arguments); }
    gtag('consent', 'update', {
      'ad_storage': 'granted',
      'ad_user_data': 'granted',
      'ad_personalization': 'granted',
      'analytics_storage': 'granted'
    });
  }

  function setDefaultConsent() {
    window.dataLayer = window.dataLayer || [];
    function gtag(){ dataLayer.push(arguments); }
    gtag('consent', 'default', {
      'ad_storage': 'denied',
      'ad_user_data': 'denied',
      'ad_personalization': 'denied',
      'analytics_storage': 'denied'
    });
  }

  function showBanner() {
    var banner = document.createElement('div');
    banner.id = 'cookie-consent-banner';
    banner.style.cssText = 'position:fixed;bottom:0;left:0;right:0;background:#0a0a0c;border-top:1px solid #2a2a30;padding:16px 24px;z-index:9999;font-family:Inter,sans-serif;display:flex;align-items:center;justify-content:center;gap:16px;flex-wrap:wrap;';
    banner.innerHTML =
      '<p style="color:#e4e4e7;font-size:0.85rem;margin:0;max-width:600px;line-height:1.5;">' +
        'This site uses cookies from Google AdSense for advertising. ' +
        'No other tracking. <a href="/privacy.html" style="color:#6366f1;text-decoration:underline;">Privacy Policy</a>' +
      '</p>' +
      '<div style="display:flex;gap:8px;flex-shrink:0;">' +
        '<button id="cookie-accept" style="padding:8px 20px;background:#6366f1;color:white;border:none;border-radius:6px;font-size:0.85rem;cursor:pointer;font-family:Inter,sans-serif;">Accept</button>' +
        '<button id="cookie-reject" style="padding:8px 20px;background:transparent;color:#8b8b94;border:1px solid #2a2a30;border-radius:6px;font-size:0.85rem;cursor:pointer;font-family:Inter,sans-serif;">Reject</button>' +
      '</div>';

    document.body.appendChild(banner);

    document.getElementById('cookie-accept').addEventListener('click', function() {
      setConsent('accepted');
      loadAdSense();
      banner.remove();
    });

    document.getElementById('cookie-reject').addEventListener('click', function() {
      setConsent('rejected');
      banner.remove();
    });
  }

  // Set default consent state (denied) before any Google scripts load
  setDefaultConsent();

  // Check consent on page load
  if (hasConsent()) {
    loadAdSense();
  } else if (localStorage.getItem(CONSENT_KEY) !== 'rejected') {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', showBanner);
    } else {
      showBanner();
    }
  }
})();
