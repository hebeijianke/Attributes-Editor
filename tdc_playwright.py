from playwright.sync_api import sync_playwright
from typing import Optional


def generate_collect(
    user_agent: str,
    entry_url: str,
    *,
    headless: bool = True,
    wait_ms_after_set_data: int = 600,
) -> str:
    """
    Generate TDC collect value using a real Chromium instance via Playwright.

    Attempts to approximate a typical desktop Chrome environment and avoid
    automation fingerprints to increase fidelity of the collected data size.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu-sandbox",
                "--disable-software-rasterizer",
                "--disable-blink-features=AutomationControlled",
                "--lang=zh-CN,zh",
                "--window-size=1920,1080",
            ],
        )

        context = browser.new_context(
            user_agent=user_agent,
            viewport={"width": 1920, "height": 1040},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            color_scheme="light",
            device_scale_factor=1.0,
            is_mobile=False,
            has_touch=False,
        )

        # Basic stealth: remove webdriver flag, add languages/plugins, spoof chrome object, WebGL vendor/renderer, userAgentData
        context.add_init_script(
            r"""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN','zh'] });
            Object.defineProperty(navigator, 'language', { get: () => 'zh-CN' });
            Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
            Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
            Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
            Object.defineProperty(navigator, 'plugins', { get: () => ({ length: 3, 0:{name:'Chrome PDF Plugin'}, 1:{name:'Chrome PDF Viewer'}, 2:{name:'Native Client'} }) });
            Object.defineProperty(navigator, 'mimeTypes', { get: () => ({ length: 2, 0:{type:'application/pdf'}, 1:{type:'application/x-nacl'} }) });
            Object.defineProperty(navigator, 'pdfViewerEnabled', { get: () => true });
            
            // userAgentData spoof
            try {
              const brands = [
                { brand: 'Chromium', version: '120' },
                { brand: 'Google Chrome', version: '120' },
                { brand: 'Not;A=Brand', version: '99' }
              ];
              Object.defineProperty(navigator, 'userAgentData', {
                get: () => ({ brands, mobile: false, platform: 'Windows', getHighEntropyValues: async (hints) => ({ brands, mobile: false, platform: 'Windows', platformVersion: '15.0.0', architecture: 'x86', model: '', uaFullVersion: '120.0.0.0', bitness: '64' }) })
              });
            } catch (e) {}
            
            // Permissions query stealth
            const originalQuery = window.navigator.permissions && window.navigator.permissions.query;
            if (originalQuery) {
              window.navigator.permissions.query = (parameters) => (
                parameters && parameters.name === 'notifications'
                  ? Promise.resolve({ state: Notification.permission })
                  : originalQuery(parameters)
              );
            }
            
            // Notification API
            try {
              if (!('Notification' in window)) {
                window.Notification = { permission: 'default', requestPermission: () => Promise.resolve('default') };
              }
            } catch(e) {}
            
            // Network Information API
            try {
              if (!('connection' in navigator)) {
                Object.defineProperty(navigator, 'connection', { get: () => ({ effectiveType: '4g', rtt: 50, downlink: 10, saveData: false }) });
              }
            } catch(e) {}
            
            // matchMedia
            try {
              if (!('matchMedia' in window)) {
                window.matchMedia = (q) => ({ matches: String(q).includes('prefers-color-scheme: light'), media: q, addListener: () => {}, removeListener: () => {}, onchange: null, addEventListener: () => {}, removeEventListener: () => {} });
              }
            } catch(e) {}
            
            // window.chrome presence
            window.chrome = window.chrome || { runtime: {} };
            window.chrome.app = window.chrome.app || { isInstalled: false };
            window.chrome.webstore = window.chrome.webstore || {};

            // Screen orientation presence
            if (!window.screen.orientation) {
              window.screen.orientation = { type: 'landscape-primary', angle: 0 };
            }

            // WebGL vendor/renderer
            try {
              const getContext = HTMLCanvasElement.prototype.getContext;
              HTMLCanvasElement.prototype.getContext = function(type, attrs){
                const ctx = getContext.call(this, type, attrs);
                if (!ctx) return ctx;
                const isGL = type && (''+type).toLowerCase().includes('webgl');
                if (!isGL) return ctx;
                const origGetParameter = ctx.getParameter && ctx.getParameter.bind(ctx);
                const UNMASKED_VENDOR_WEBGL = 0x9245; // 37445
                const UNMASKED_RENDERER_WEBGL = 0x9246; // 37446
                const overrides = {};
                overrides[UNMASKED_VENDOR_WEBGL] = 'Google Inc.';
                overrides[UNMASKED_RENDERER_WEBGL] = 'ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0, D3D11)';
                ctx.getParameter = function(p){
                  if (p in overrides) return overrides[p];
                  try { return origGetParameter ? origGetParameter(p) : 0; } catch(e) { return 0; }
                };
                const origGetSupportedExtensions = ctx.getSupportedExtensions && ctx.getSupportedExtensions.bind(ctx);
                ctx.getSupportedExtensions = function(){
                  const base = origGetSupportedExtensions ? origGetSupportedExtensions() || [] : [];
                  if (base.indexOf('WEBGL_lose_context') === -1) base.push('WEBGL_lose_context');
                  return base;
                };
                return ctx;
              };
            } catch(e) {}
        """
        )

        page = context.new_page()
        page.goto(entry_url, wait_until="load")

        # Small real-user like actions to let APIs initialize
        try:
            page.mouse.move(200, 200)
            page.mouse.wheel(0, 200)
        except Exception:
            pass

        # Inject TDC script and wait until it is available
        tdc_base = "https://turing.captcha.qcloud.com/tdc.js"
        page.add_script_tag(url=tdc_base)
        page.wait_for_function("() => window.TDC && typeof window.TDC.setData === 'function'", timeout=10000)

        # Run setData and then extract collect string
        page.evaluate("() => { try { TDC.setData({isNewEntry:1}); } catch(e) {} }")
        if wait_ms_after_set_data > 0:
            page.wait_for_timeout(max(600, wait_ms_after_set_data))

        collect: Optional[str] = page.evaluate(
            "() => { try { return TDC.getData(true) || ''; } catch(e) { return ''; } }"
        )

        browser.close()
        return collect or ""


if __name__ == "__main__":
    UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    url = "https://auth.smartedu.cn/uias/login"
    out = generate_collect(UA, url, headless=True)
    print(out)
    print(len(out))

