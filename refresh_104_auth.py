import os
import boto3
from playwright.sync_api import sync_playwright

BUCKET = "autojobber-config-381076011493"
AUTH_PATH = "auth_104.json"

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://www.104.com.tw/")

        print("==> Log in to 104 in the browser window, then come back here and press Enter...")
        input()

        context.storage_state(path=AUTH_PATH)
        print(f"==> Session saved to {AUTH_PATH}")
        browser.close()

    session = boto3.Session(profile_name="personal")
    s3 = session.client("s3")
    s3.upload_file(AUTH_PATH, BUCKET, AUTH_PATH)
    print(f"==> Uploaded to s3://{BUCKET}/{AUTH_PATH}")

if __name__ == "__main__":
    main()
