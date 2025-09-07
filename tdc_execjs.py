import re
import requests
import execjs

TDC_URL = "https://turing.captcha.qcloud.com/tdc.js"


def _fetch_tdc_js(user_agent: str) -> str:
    resp = requests.get(
        TDC_URL,
        headers={
            "User-Agent": user_agent,
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://turing.captcha.qcloud.com/",
            "Origin": "https://turing.captcha.qcloud.com",
        },
        timeout=18,
    )
    if resp.ok and len(resp.text) >= 10000:
        return resp.text
    raise RuntimeError(
        f"failed to fetch tdc.js: status={resp.status_code}, len={len(resp.text)}"
    )


def get_collect(user_agent: str, entry_url: str) -> str:
    tdc_js = _fetch_tdc_js(user_agent)

    env = r"""
var window = this;
window.window = window;
window.self = window;
window.top = window;
window.parent = window;

function _noop(){}

// Basic URL/location wiring
var __LOC__ = (function(){
  var a = document && document.createElement ? document.createElement('a') : null;
  var href = '__ENTRY__';
  if (a) { a.href = href; }
  return {
    href: href,
    protocol: 'https:',
    host: 'auth.smartedu.cn',
    hostname: 'auth.smartedu.cn',
    port: '',
    pathname: '/uias/login',
    search: '',
    hash: '',
    assign: _noop,
    replace: _noop,
    toString: function(){ return href; }
  };
})();

var __cookieStore = '';
var document = {};
Object.defineProperty(this, 'document', { value: document, writable: false });

document.addEventListener = _noop;
document.removeEventListener = _noop;
document.hidden = false;
document.visibilityState = 'visible';
document.referrer = 'https://auth.smartedu.cn/';
document.URL = __LOC__.href;
document.location = __LOC__;
document.documentElement = { clientWidth: 1920, clientHeight: 1040 };
document.cookie = __cookieStore;
Object.defineProperty(document, 'cookie', {
  get: function(){ return __cookieStore; },
  set: function(v){ __cookieStore = (__cookieStore ? (__cookieStore + '; ') : '') + String(v); }
});

// Minimal DOM emulation sufficient for canvas and script injection code paths
document.createElement = function(name){
  if (name === 'canvas') {
    return (function(){
      var ctx2d = {
        measureText: function(){ return { width: 100 }; },
        fillRect: _noop,
        strokeRect: _noop,
        beginPath: _noop,
        fillText: _noop,
        arc: _noop,
        quadraticCurveTo: _noop,
        bezierCurveTo: _noop,
        moveTo: _noop,
        lineTo: _noop,
        closePath: _noop,
        getImageData: function(){ return { data: new Uint8ClampedArray(400) }; },
        // text metrics and fonts
        font: '16px Arial'
      };
      var ctxWebGL = {
        getParameter: function(p){
          var UNMASKED_VENDOR_WEBGL = 0x9245;
          var UNMASKED_RENDERER_WEBGL = 0x9246;
          if (p === UNMASKED_VENDOR_WEBGL) return 'Google Inc.';
          if (p === UNMASKED_RENDERER_WEBGL) return 'ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0, D3D11)';
          return 0;
        },
        getSupportedExtensions: function(){ return ['WEBGL_lose_context','OES_texture_float']; },
        getExtension: function(){ return null; },
        canvas: null
      };
      var canvas = {
        width: 300,
        height: 150,
        getContext: function(type){
          if (type === '2d') return ctx2d;
          if (type === 'webgl' || type === 'experimental-webgl' || type === 'webgl2') return ctxWebGL;
          return null;
        },
        toDataURL: function(){ return 'data:image/png;base64,'; }
      };
      ctxWebGL.canvas = canvas;
      return canvas;
    })();
  }
  return { style: {} };
};

document.getElementById = function(){ return null; };
document.body = { appendChild: _noop, clientWidth:1920, clientHeight:1040 };

window.document = document;
window.location = __LOC__;
window.origin = 'https://auth.smartedu.cn';

// Navigator and related fingerprints
var navigator = {
  userAgent: '__UA__',
  language: 'zh-CN',
  languages: ['zh-CN','zh'],
  platform: 'Win32',
  maxTouchPoints: 0,
  hardwareConcurrency: 8,
  webdriver: false,
  vendor: 'Google Inc.',
  deviceMemory: 8,
  plugins: { length: 3, 0:{name:'Chrome PDF Plugin'}, 1:{name:'Chrome PDF Viewer'}, 2:{name:'Native Client'} },
  mimeTypes: { length: 2, 0:{type:'application/pdf'}, 1:{type:'application/x-nacl'} },
  permissions: {
    query: function(params){
      if (params && params.name === 'notifications') {
        return Promise.resolve({ state: 'default' });
      }
      return Promise.resolve({ state: 'granted' });
    }
  }
};
window.navigator = navigator;

// userAgentData
window.navigator.userAgentData = {
  brands: [
    { brand: 'Chromium', version: '120' },
    { brand: 'Google Chrome', version: '120' },
    { brand: 'Not;A=Brand', version: '99' }
  ],
  mobile: false,
  platform: 'Windows',
  getHighEntropyValues: function(){ return Promise.resolve({
    brands: [
      { brand: 'Chromium', version: '120' },
      { brand: 'Google Chrome', version: '120' },
      { brand: 'Not;A=Brand', version: '99' }
    ],
    mobile: false,
    platform: 'Windows',
    platformVersion: '15.0.0',
    architecture: 'x86',
    model: '',
    uaFullVersion: '120.0.0.0',
    bitness: '64'
  }); }
};

// Screen and window metrics
var screen = { width:1920, height:1080, availWidth:1920, availHeight:1040, colorDepth:24, pixelDepth:24 };
screen.orientation = { type: 'landscape-primary', angle: 0 };
window.screen = screen;
window.innerWidth = 1920;
window.innerHeight = 1040;
window.outerWidth = 1920;
window.outerHeight = 1080;
window.devicePixelRatio = 1;
window.pageXOffset = 0;
window.pageYOffset = 0;
// matchMedia
window.matchMedia = function(q){ return { matches: String(q).indexOf('prefers-color-scheme: light') !== -1, media: q, addListener: function(){}, removeListener: function(){}, onchange: null, addEventListener: function(){}, removeEventListener: function(){} }; };

// Storage
var __ls = {};
var localStorage = { getItem:function(k){return __ls[k]||null;}, setItem:function(k,v){__ls[k]=String(v);}, removeItem:function(k){delete __ls[k];} };
var __ss = {};
var sessionStorage = { getItem:function(k){return __ss[k]||null;}, setItem:function(k,v){__ss[k]=String(v);}, removeItem:function(k){delete __ss[k];} };
window.localStorage = localStorage;
window.sessionStorage = sessionStorage;

// Performance
var __t0 = Date.now();
var performance = {
  now: function(){ return Date.now() - __t0; },
  timeOrigin: __t0,
  timing: {}
};
window.performance = performance;

// Audio
var AudioContext = function(){};
var webkitAudioContext = AudioContext;
window.AudioContext = AudioContext;
window.webkitAudioContext = webkitAudioContext;

// Crypto
var crypto = {
  getRandomValues: function(arr){
    for (var i=0;i<arr.length;i++) { arr[i] = Math.floor(Math.random()*256) & 255; }
    return arr;
  },
  subtle: {}
};
window.crypto = crypto;

// Chrome presence
window.chrome = window.chrome || { runtime: {} };
window.chrome.app = window.chrome.app || { isInstalled: false };
window.chrome.webstore = window.chrome.webstore || {};

// Events
window.addEventListener = _noop;
window.removeEventListener = _noop;

// atob/btoa for base64
if (typeof btoa === 'undefined') {
  function btoa(input){
    var chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=';
    var str = String(input);
    var output = '';
    for (var block, charCode, i = 0, map = chars; str.charAt(i | 0) || (map = '=', i % 1); output += map.charAt(63 & block >> 8 - i % 1 * 8)) {
      charCode = str.charCodeAt(i += 3/4);
      if (charCode > 0xFF) throw new Error('btoa: invalid char');
      block = (block << 8) | charCode;
    }
    return output;
  }
}
if (typeof atob === 'undefined') {
  function atob(input){
    var str = String(input).replace(/=+$/, '');
    var chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=';
    var output = '';
    if (str.length % 4 == 1) throw new Error('atob: bad length');
    for (var bc = 0, bs, buffer, i = 0; (buffer = str.charAt(i++)); ~buffer && (bs = bc % 4 ? bs * 64 + buffer : buffer, bc++ % 4) ? output += String.fromCharCode(255 & bs >> (-2 * bc & 6)) : 0) {
      buffer = chars.indexOf(buffer);
    }
    return output;
  }
}

// XHR minimal
var XMLHttpRequest = function(){ this.open=function(){}, this.send=function(){}, this.setRequestHeader=function(){} };
window.XMLHttpRequest = XMLHttpRequest;

// Network Information
Object.defineProperty(navigator, 'connection', { get: function(){ return { effectiveType: '4g', rtt: 50, downlink: 10, saveData: false }; } });

// Notification
window.Notification = window.Notification || { permission: 'default', requestPermission: function(){ return Promise.resolve('default'); } };

// Battery
navigator.getBattery = navigator.getBattery || function(){ return Promise.resolve({ charging: true, chargingTime: 0, dischargingTime: Infinity, level: 0.76, addEventListener:_noop, removeEventListener:_noop }); };

// Performance memory
performance.memory = performance.memory || { totalJSHeapSize: 30e6, usedJSHeapSize: 20e6, jsHeapSizeLimit: 2e9 };

// Visibility API
Object.defineProperty(document, 'visibilityState', { get: function(){ return 'visible'; } });
Object.defineProperty(document, 'hidden', { get: function(){ return false; } });

"""

    boot = r"""
// Let tdc setup, then gather
if (window.TDC && typeof window.TDC.setData === 'function') {
  try { window.TDC.setData({isNewEntry:1}); } catch(e) {}
}
function __get_collect__(){
  try {
    if (!window.TDC || typeof window.TDC.getData !== 'function') return '';
    var v = window.TDC.getData(true);
    return (typeof v === 'string') ? v : '';
  } catch(e) {
    return 'Err:' + (e && e.message ? e.message : String(e));
  }
}
"""

    env = env.replace("__UA__", user_agent)
    env = env.replace("__ENTRY__", entry_url)

    ctx = execjs.compile(env + tdc_js + boot)
    result = ctx.call("__get_collect__")
    if isinstance(result, str) and result.startswith("Err:"):
        raise RuntimeError(result)
    return result or ""


if __name__ == "__main__":
    UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    url = "https://auth.smartedu.cn/uias/login"
    out = get_collect(UA, url)
    print(f"collect: {out}")
    print(f"len: {len(out)}")

