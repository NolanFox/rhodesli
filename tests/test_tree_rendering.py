import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        page.on("console", lambda msg: print(f"Browser console ({msg.type}): {msg.text}"))
        page.on("pageerror", lambda err: print(f"Browser error: {err}\nStack trace:\n{err.stack}"))
        
        print("Navigating to local server...")
        try:
            await page.goto("http://127.0.0.1:5001/tree")
            await page.wait_for_timeout(3000)
            await page.screenshot(path="/Users/nolanfox/.gemini/antigravity/brain/edd8a1fe-7af6-4a44-bb92-3a1252bc35fe/playwright_screenshot.png")
            print("Screenshot saved.")
        except Exception as e:
            print(f"Failed to navigate: {e}")
            
        await browser.close()

asyncio.run(run())
