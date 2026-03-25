/**
 * Google Consent Mode v2 - Default State
 * Sets consent defaults BEFORE any Google scripts load.
 * Google's Funding Choices CMP (configured in AdSense dashboard)
 * handles the actual consent UI and updates.
 */
(function() {
  'use strict';

  // Set default consent state (denied) before Google scripts execute
  window.dataLayer = window.dataLayer || [];
  function gtag(){ dataLayer.push(arguments); }

  gtag('consent', 'default', {
    'ad_storage': 'denied',
    'ad_user_data': 'denied',
    'ad_personalization': 'denied',
    'analytics_storage': 'denied',
    'wait_for_update': 500
  });

  // Google Funding Choices CMP will call gtag('consent', 'update', ...)
  // when the user makes a choice. No custom banner needed.
})();
