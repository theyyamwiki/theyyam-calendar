/* Theyyam Calendar – നോട്ടീസ് ഫോട്ടോ അപ്‌ലോഡ് (index.html ലെ ഡയലോഗിലും upload.html ലും ഉപയോഗിക്കുന്നു) */
(function () {
  'use strict';

  var ENDPOINT = 'https://script.google.com/macros/s/AKfycbxqtwxuyfahkhpr0QG9RKaXDNF6oJ7eqBDjIWXDMrvncC6XjI2xzrpKtCUU49wa73_f/exec';
  var MAX_B64 = 2800000; // സെർവർ പരിധി 3,000,000

  var TXT = {
    ml: {
      title: 'നോട്ടീസ് സമർപ്പിക്കുക',
      intro: 'കളിയാട്ടത്തിന്റെ നോട്ടീസ് ഫോട്ടോ തിരഞ്ഞെടുത്താൽ മതി. ബാക്കി ഞങ്ങൾ നോക്കാം. പരിശോധിച്ച ശേഷം കലണ്ടറിൽ ചേർക്കും.',
      pick: '📷 നോട്ടീസ് ഫോട്ടോ തിരഞ്ഞെടുക്കൂ',
      send: 'അയക്കുക',
      sending: 'അയക്കുന്നു…',
      ok: '✔ ലഭിച്ചു, നന്ദി! പരിശോധിച്ച ശേഷം കലണ്ടറിൽ ചേർക്കും.',
      bad: 'ഈ ഫയൽ വായിക്കാൻ പറ്റിയില്ല. മറ്റൊരു ചിത്രം തിരഞ്ഞെടുക്കൂ.',
      net: 'നെറ്റ്‌വർക്ക് പ്രശ്നം, വീണ്ടും ശ്രമിക്കൂ.',
      fail: 'അയക്കാൻ പറ്റിയില്ല, വീണ്ടും ശ്രമിക്കൂ.',
      big: 'ചിത്രം വളരെ വലുതാണ്. മറ്റൊരു ചിത്രം തിരഞ്ഞെടുക്കൂ.'
    },
    en: {
      title: 'Submit a Notice',
      intro: 'Just choose a photo of the festival notice. We will take care of the rest and add it to the calendar after checking.',
      pick: '📷 Choose notice photo',
      send: 'Send',
      sending: 'Sending…',
      ok: '✔ Received, thank you! It will be added to the calendar after checking.',
      bad: 'Could not read this file. Please choose another image.',
      net: 'Network problem, please try again.',
      fail: 'Could not send, please try again.',
      big: 'This image is too large. Please choose another one.'
    },
    hi: {
      title: 'सूचना जमा करें',
      intro: 'कलियाट्टम की सूचना (नोटिस) की फोटो चुनें, बाकी हम देख लेंगे। जाँच के बाद इसे कैलेंडर में जोड़ा जाएगा।',
      pick: '📷 सूचना की फोटो चुनें',
      send: 'भेजें',
      sending: 'भेज रहे हैं…',
      ok: '✔ मिल गया, धन्यवाद! जाँच के बाद कैलेंडर में जोड़ा जाएगा।',
      bad: 'यह फ़ाइल पढ़ी नहीं जा सकी। कृपया दूसरी फोटो चुनें।',
      net: 'नेटवर्क समस्या, कृपया फिर प्रयास करें।',
      fail: 'भेजा नहीं जा सका, कृपया फिर प्रयास करें।',
      big: 'यह फोटो बहुत बड़ी है। कृपया दूसरी चुनें।'
    }
  };

  function lang() {
    try { var l = window.localStorage.getItem('theyyam_lang'); if (TXT[l]) return l; } catch (e) { }
    try { var q = new URLSearchParams(window.location.search).get('lang'); if (TXT[q]) return q; } catch (e) { }
    return 'en';
  }
  function T(k) { var l = lang(); return (TXT[l] && TXT[l][k]) || TXT.en[k]; }

  function addStyle() {
    if (document.getElementById('nu-style')) return;
    var s = document.createElement('style');
    s.id = 'nu-style';
    s.textContent =
      '.nu{font-family:inherit;color:#333}' +
      '.nu-intro{margin:0 0 12px;font-size:.92em;line-height:1.6}' +
      '.nu-pick{display:block;text-align:center;padding:16px 10px;border:2px dashed #c62828;border-radius:12px;color:#c62828;font-weight:700;font-size:1.05em;cursor:pointer;background:#fffaf6}' +
      '.nu-pick input{display:none}' +
      '.nu-prev{display:block;max-width:100%;max-height:60vh;margin:10px auto 0;border-radius:8px;border:1px solid #ddd}' +
      '.nu-prev[hidden]{display:none}' +
      '.nu-hp{position:absolute;left:-9999px;height:0;overflow:hidden}' +
      '.nu-send{display:block;width:100%;margin-top:12px;padding:12px;font-size:1.05em;font-weight:700;font-family:inherit;border:0;border-radius:8px;background:#2e7d32;color:#fff;cursor:pointer}' +
      '.nu-send:disabled{opacity:.45;cursor:default}' +
      '.nu-status{margin-top:12px;font-size:.95em;line-height:1.5;text-align:center}' +
      '.nu-status.nu-ok{color:#2e7d32;font-weight:700}' +
      '.nu-status.nu-err{color:#c62828;font-weight:700}';
    document.head.appendChild(s);
  }

  // 9x8 ചിത്രത്തിൽ നിന്ന് 64-bit dHash (ഒരേ നോട്ടീസ് വീണ്ടും വരുന്നത് കണ്ടെത്താൻ)
  function dHash(img) {
    var c = document.createElement('canvas'); c.width = 9; c.height = 8;
    var x = c.getContext('2d'); x.drawImage(img, 0, 0, 9, 8);
    var d = x.getImageData(0, 0, 9, 8).data, g = [], i;
    for (i = 0; i < 72; i++) g.push(0.299 * d[i * 4] + 0.587 * d[i * 4 + 1] + 0.114 * d[i * 4 + 2]);
    var bits = '';
    for (var r = 0; r < 8; r++) for (var k = 0; k < 8; k++) bits += g[r * 9 + k] > g[r * 9 + k + 1] ? '1' : '0';
    var hex = '';
    for (i = 0; i < 64; i += 4) hex += parseInt(bits.substr(i, 4), 2).toString(16);
    return hex;
  }

  function device() {
    try {
      var d = window.localStorage.getItem('tc_dev');
      if (!d) { d = 'd' + Math.random().toString(36).slice(2) + Date.now().toString(36); window.localStorage.setItem('tc_dev', d); }
      return d;
    } catch (e) { return 'nodev'; }
  }

  // വലിപ്പവും ക്വാളിറ്റിയും കുറച്ച് സെർവർ പരിധിക്കുള്ളിൽ ആക്കുന്നു
  function encode(img) {
    var sizes = [1600, 1200, 900], quals = [0.82, 0.7], out = '';
    for (var a = 0; a < sizes.length; a++) {
      var s = Math.min(1, sizes[a] / Math.max(img.naturalWidth, img.naturalHeight));
      var c = document.createElement('canvas');
      c.width = Math.max(1, Math.round(img.naturalWidth * s));
      c.height = Math.max(1, Math.round(img.naturalHeight * s));
      c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
      for (var b = 0; b < quals.length; b++) {
        out = c.toDataURL('image/jpeg', quals[b]);
        if (out.length - 23 <= MAX_B64) return out;
      }
    }
    return '';
  }

  function mount(root) {
    addStyle();
    root.innerHTML =
      '<div class="nu"><p class="nu-intro"></p>' +
      '<label class="nu-pick"><input type="file" accept="image/*"><span></span></label>' +
      '<img class="nu-prev" alt="" hidden>' +
      '<div class="nu-hp" aria-hidden="true"><input tabindex="-1" autocomplete="off"></div>' +
      '<button type="button" class="nu-send" disabled></button>' +
      '<div class="nu-status" role="status"></div></div>';
    var $ = function (q) { return root.querySelector(q); };
    var fileEl = $('.nu-pick input'), prev = $('.nu-prev'), sendBtn = $('.nu-send'), st = $('.nu-status'), hp = $('.nu-hp input');
    $('.nu-intro').textContent = T('intro');
    $('.nu-pick span').textContent = T('pick');
    sendBtn.textContent = T('send');

    var dataUrl = '', phash = '', busy = false;
    function status(msg, cls) { st.textContent = msg || ''; st.className = 'nu-status' + (cls ? ' ' + cls : ''); }
    function refresh() { sendBtn.disabled = busy || !dataUrl; }

    fileEl.addEventListener('change', function () {
      var f = fileEl.files && fileEl.files[0];
      dataUrl = ''; phash = ''; prev.hidden = true; status(''); refresh();
      if (!f) return;
      var url = URL.createObjectURL(f), img = new Image();
      img.onload = function () {
        try {
          var out = encode(img);
          if (!out) { status(T('big'), 'nu-err'); return; }
          dataUrl = out; phash = dHash(img);
          prev.src = dataUrl; prev.hidden = false;
        } catch (e) { status(T('bad'), 'nu-err'); }
        URL.revokeObjectURL(url); refresh();
      };
      img.onerror = function () { URL.revokeObjectURL(url); status(T('bad'), 'nu-err'); };
      img.src = url;
    });

    sendBtn.addEventListener('click', function () {
      if (busy || !dataUrl) return;
      busy = true; refresh(); sendBtn.textContent = T('sending'); status('');
      fetch(ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'text/plain;charset=utf-8' }, // preflight ഒഴിവാക്കാൻ
        body: JSON.stringify({
          image: dataUrl.split(',')[1], mime: 'image/jpeg', phash: phash,
          token: 'none', device: device(), hp: hp.value
        })
      }).then(function (r) { return r.json(); }).then(function (j) {
        if (j && j.ok) {
          status(T('ok'), 'nu-ok');
          dataUrl = ''; phash = ''; prev.hidden = true; fileEl.value = '';
        } else {
          status((j && j.error) || T('fail'), 'nu-err');
        }
      }).catch(function () {
        status(T('net'), 'nu-err');
      }).then(function () {
        busy = false; sendBtn.textContent = T('send'); refresh();
      });
    });
  }

  window.NoticeUpload = { mount: mount, text: T };
})();
