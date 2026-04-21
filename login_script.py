# 文件名: login_script.py
# 作用: 自动登录 ClawCloud Run，支持 GitHub 账号密码 + 2FA 自动验证

import os
import time
import random
import pyotp  # 用于生成 2FA 验证码
import requests  # 用于发送 HTTP 请求
from playwright.sync_api import sync_playwright

def send_pushplus_notification(title, content, token=None):
    """
    发送 pushplus 通知
    :param title: 通知标题
    :param content: 通知内容
    :param token: pushplus token (如果不提供，从环境变量 PUSHPLUS_TOKEN 读取)
    :return: 是否发送成功
    """
    if not token:
        token = os.environ.get("PUSHPLUS_TOKEN")
    
    if not token:
        print("⚠️ 未配置 PUSHPLUS_TOKEN，跳过通知发送")
        return False
    
    try:
        url = "http://www.pushplus.plus/send"
        data = {
            "token": token,
            "title": title,
            "content": content,
            "template": "html"  # 使用 HTML 模板
        }
        response = requests.post(url, json=data, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 0:
                print(f"✅ pushplus 通知发送成功: {title}")
                return True
            else:
                print(f"⚠️ pushplus 通知发送失败: {result.get('msg')}")
                return False
        else:
            print(f"⚠️ pushplus 请求失败: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ pushplus 通知发送异常: {e}")
        return False

def random_delay(min_seconds=0.5, max_seconds=2.0):
    """模拟人类操作延迟"""
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)

def human_like_type(page, selector, text, delay_range=(50, 150)):
    """模拟人类输入，逐字符打字"""
    element = page.locator(selector)
    element.click()
    random_delay(0.2, 0.5)
    for char in text:
        element.type(char)
        time.sleep(random.uniform(delay_range[0] / 1000, delay_range[1] / 1000))
    random_delay(0.3, 0.8)

def run_login():
    # 1. 获取环境变量中的敏感信息
    username = os.environ.get("GH_USERNAME")
    password = os.environ.get("GH_PASSWORD")
    totp_secret = os.environ.get("GH_2FA_SECRET")

    if not username or not password:
        print("❌ 错误: 必须设置 GH_USERNAME 和 GH_PASSWORD 环境变量。")
        return

    print("🚀 [Step 1] 启动浏览器...")
    with sync_playwright() as p:
        # 启动浏览器，添加反爬虫措施
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',  # 隐藏自动化特征
                '--disable-dev-shm-usage',  # 禁用共享内存使用
                '--no-sandbox',  # 禁用沙箱（某些环境需要）
            ]
        )
        
        # 设置反爬虫的 User-Agent 和其他识别信息
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]
        
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=random.choice(user_agents),  # 随机 User-Agent
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            }
        )
        
        # 隐藏 webdriver 特征
        page = context.new_page()
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false,
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3],
            });
        """)

        # 2. 访问 ClawCloud 登录页
        target_url = "https://ap-northeast-1.run.claw.cloud/"
        print(f"🌐 [Step 2] 正在访问: {target_url}")
        page.goto(target_url)
        page.wait_for_load_state("networkidle")
        random_delay(1, 2)  # 加入随机延迟

        # 3. 点击 GitHub 登录按钮
        print("🔍 [Step 3] 寻找 GitHub 按钮...")
        try:
            # 精确查找包含 'GitHub' 文本的按钮
            login_button = page.locator("button:has-text('GitHub')")
            login_button.wait_for(state="visible", timeout=10000)
            random_delay(0.5, 1.5)  # 随机延迟再点击
            login_button.click()
            print("✅ 按钮已点击")
        except Exception as e:
            print(f"⚠️ 未找到 GitHub 按钮 (可能已自动登录或页面变动): {e}")

        # 4. 处理 GitHub 登录表单
        print("⏳ [Step 4] 等待跳转到 GitHub...")
        try:
            # 等待 URL 变更为 github.com
            page.wait_for_url(lambda url: "github.com" in url, timeout=15000)
            
            # 如果是在登录页，则填写账号密码（模拟人类操作）
            if "login" in page.url:
                print("🔒 输入账号密码...")
                random_delay(0.5, 1)  # 等待页面完全加载
                human_like_type(page, "#login_field", username)
                human_like_type(page, "#password", password)
                random_delay(0.5, 1.5)  # 按钮前再随机等待
                page.click("input[name='commit']") # 点击登录按钮
                print("📤 登录表单已提交")
        except Exception as e:
            print(f"ℹ️ 跳过账号密码填写 (可能已自动登录): {e}")

        # 5. 【核心】处理 2FA 双重验证 (解决异地登录拦截)
        # 给页面一点时间跳转
        page.wait_for_timeout(random.randint(2500, 3500))  # 随机延迟
        
        # 检查 URL 是否包含 two-factor 或页面是否有验证码输入框
        if "two-factor" in page.url or page.locator("#app_totp").count() > 0:
            print("🔐 [Step 5] 检测到 2FA 双重验证请求！")
            
            if totp_secret:
                print("🔢 正在计算动态验证码 (TOTP)...")
                random_delay(0.5, 1)
                try:
                    # 使用密钥生成当前的 6 位验证码
                    totp = pyotp.TOTP(totp_secret)
                    token = totp.now()
                    print(f"   生成的验证码: {token}")
                    
                    # 填入 GitHub 的验证码输入框（模拟人类逐字输入）
                    human_like_type(page, "#app_totp", token, delay_range=(100, 200))
                    print("✅ 验证码已填入，GitHub 应会自动跳转...")
                    
                    # 某些情况下可能需要手动回车，这里做个保险
                    # page.keyboard.press("Enter")
                except Exception as e:
                    print(f"❌ 填入验证码失败: {e}")
            else:
                print("❌ 致命错误: 检测到 2FA 但未配置 GH_2FA_SECRET Secret！")
                exit(1)
        else:
            print("ℹ️ 未检测到 2FA 验证页面")

        # 6. 处理授权确认页 (Authorize App)
        # 第一次登录可能会出现
        page.wait_for_timeout(3000)
        if "authorize" in page.url.lower():
            print("⚠️ 检测到授权请求，尝试点击 Authorize...")
            try:
                page.click("button:has-text('Authorize')", timeout=5000)
            except:
                pass

        # 7. 等待最终跳转结果
        print("⏳ [Step 7] 等待跳转回 ClawCloud 控制台 (约30秒)...")
        # 强制等待较长时间，确保页面完全重定向
        page.wait_for_timeout(30000)
        
        final_url = page.url
        print(f"📍 最终页面 URL: {final_url}")
        
        # 截图保存，用于 GitHub Actions 查看结果
        page.screenshot(path="login_result.png")
        print("📸 已保存结果截图: login_result.png")

        # 8. 验证是否成功
        # 成功的标志：URL 不再是 GitHub，且包含控制台特征
        is_success = False
        
        # 检查点 A: 页面包含特定文字 (最准确)
        if page.get_by_text("App Launchpad").count() > 0 or page.get_by_text("Devbox").count() > 0:
            is_success = True
        # 检查点 B: URL 包含 console 特征
        elif "private-team" in final_url or "console" in final_url:
            is_success = True
        # 检查点 C: 只要不是登录页也不是 GitHub 验证页
        elif "signin" not in final_url and "github.com" not in final_url:
            is_success = True

        if is_success:
            print("🎉🎉🎉 登录成功！任务完成。")
            send_pushplus_notification(
                title="ClawCloud 自动登录成功 ✅",
                content="<h3>🎉 ClawCloud 自动登录成功！</h3><p><strong>账号:</strong> " + username + "</p><p><strong>时间:</strong> " + time.strftime("%Y-%m-%d %H:%M:%S") + "</p><p>祝您使用愉快！</p>"
            )
        else:
            print("😭😭😭 登录失败。请下载 login_result.png 查看原因。")
            send_pushplus_notification(
                title="ClawCloud 自动登录失败 ❌",
                content="<h3>❌ ClawCloud 自动登录失败！</h3><p><strong>账号:</strong> " + username + "</p><p><strong>时间:</strong> " + time.strftime("%Y-%m-%d %H:%M:%S") + "</p><p>请检查日志并手动处理。</p>"
            )
            exit(1) # 抛出错误代码，让 Action 变红

        browser.close()

if __name__ == "__main__":
    run_login()