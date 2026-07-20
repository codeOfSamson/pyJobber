import os
import tempfile
import boto3
from patchright.sync_api import sync_playwright
from browser.browser import bypass_cloudflare_challenge

BUCKET = "autojobber-config-381076011493"
AUTH_PATH = "auth_104.json"

def main():
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=tempfile.mkdtemp(),
            headless=False,
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://www.104.com.tw/")
        bypass_cloudflare_challenge(page)

        print("==> Log in to 104 in the browser window, then come back here and press Enter...")
        input()

        context.storage_state(path=AUTH_PATH)
        print(f"==> Session saved to {AUTH_PATH}")
        context.close()

    session = boto3.Session(profile_name="personal")
    s3 = session.client("s3")
    s3.upload_file(AUTH_PATH, BUCKET, AUTH_PATH)
    print(f"==> Uploaded to s3://{BUCKET}/{AUTH_PATH}")

if __name__ == "__main__":
    main()
