import time
import os
import base64
import sys
import re
import glob
from html import escape
from seleniumbase import SB
import ddddocr
try:
    import requests
except Exception:
    requests = None

# ==========================================
# 1. 网站配置区域
# ==========================================
CONFIG = {
    "target_url": "https://nat.freecloud.ltd/login",
    "username_selector": "#emailInp",             
    "password_selector": "#emailPwdInp",          
    "captcha_img_selector": "#allow_login_email_captcha",          
    "captcha_input_selector": "#captcha_allow_login_email_captcha", 
    "login_btn_selector": 'button[type="submit"]',
    
    "user_center_selector": 'a[href="clientarea"]',
    
    # 签到页面的元素定位器
    "sign_in_url": 'https://nat.freecloud.ltd/addons?_plugin=19&_controller=index&_action=index',
    "sign_in_btn_selector": 'button[onclick="showMathVerification()"]', 
    "math_question_selector": '#mathQuestion',                       
    "math_input_selector": '#userAnswer',                            
    "verify_btn_selector": 'button[onclick="checkAnswer()"]',        
    "popup_content_selector": ".layui-layer-content", 
    "popup_confirm_btn_selector": ".layui-layer-btn0", 
    "points_balance_selector": "div.alert-success span",
    
    # 云服务器续费流程的元素定位器
    "server_list_url": "https://nat.freecloud.ltd/service?groupid=305", 
    "server_checkbox_selector": '.row-checkbox',              
    "list_renew_btn_selector": '#readBtn',                    
    "confirm_renew_btn_selector": '.xfSubmit',          
    "order_pay_btn_selector": '#payamount',                   
    "modal_pay_btn_selector": 'button.pay-now'                
}

os.makedirs("screenshots", exist_ok=True)

def take_screenshot(sb, step_name, username="system"):
    safe_name = username.replace("@", "_").replace(".", "_")
    filepath = f"screenshots/{safe_name}_{step_name}.png"
    try:
        sb.save_screenshot(filepath)
        print(f"    📸 已截图保存: {filepath}")
        return filepath
    except Exception as e:
        print(f"    ⚠️ 截图失败 ({filepath}): {e}")
        return None


def click_first_available(sb, selectors, timeout=4, use_js=True):
    """依次尝试多个 CSS/XPath 选择器，适配网站按钮 class 变化。"""
    last_error = None
    for selector in selectors:
        try:
            sb.wait_for_element_visible(selector, timeout=timeout)
            if use_js:
                sb.js_click(selector)
            else:
                sb.click(selector)
            print(f"    ✅ 已点击按钮: {selector}")
            return selector
        except Exception as e:
            last_error = e
            print(f"    ⚠️ 未找到/无法点击: {selector}")
    raise Exception(f"所有备用按钮选择器均失败: {selectors}; last_error={last_error}")


def click_by_text(sb, texts):
    """通过按钮/链接文本点击，避免 class 变化导致续约流程中断。"""
    script = """
    const texts = arguments[0];
    const selectors = [
      '.layui-layer-btn0', '.layui-layer-btn a', '.layui-layer-btn1',
      'button.pay-now', '#payamount', '.payamount', '.xfSubmit',
      'button', 'a', 'input[type=button]', 'input[type=submit]'
    ];
    const nodes = Array.from(document.querySelectorAll(selectors.join(',')))
      .filter(el => el && el.offsetParent !== null)
      .reverse();
    for (const t of texts) {
      const hit = nodes.find(el => ((el.innerText || el.value || el.getAttribute('title') || '').trim()).includes(t));
      if (hit) { hit.scrollIntoView({block:'center'}); hit.click(); return t; }
    }
    return null;
    """
    clicked = sb.execute_script(script, texts)
    if clicked:
        print(f"    ✅ 已按文本点击按钮: {clicked}")
        return clicked
    raise Exception(f"未找到包含这些文本的按钮: {texts}")


def click_last_submit_or_confirm(sb):
    """最后兜底：优先点击页面/弹窗中靠后的确认、支付、提交按钮。"""
    script = """
    const keywords = ['确认支付', '确认付款', '余额支付', '立即支付', '支付', '确认', '确定', '提交'];
    const selectors = [
      '.layui-layer-btn0', '.layui-layer-btn a', '.layui-layer-btn1',
      'button.pay-now', '#payamount', '.payamount', '.xfSubmit',
      'button', 'a', 'input[type=button]', 'input[type=submit]'
    ];
    const nodes = Array.from(document.querySelectorAll(selectors.join(',')))
      .filter(el => el && el.offsetParent !== null)
      .reverse();
    for (const kw of keywords) {
      const hit = nodes.find(el => ((el.innerText || el.value || el.getAttribute('title') || '').trim()).includes(kw));
      if (hit) { hit.scrollIntoView({block:'center'}); hit.click(); return kw; }
    }
    const submit = nodes.find(el => (el.tagName || '').toLowerCase() === 'button' || (el.type || '').toLowerCase() === 'submit');
    if (submit) { submit.scrollIntoView({block:'center'}); submit.click(); return '最后一个可见提交按钮'; }
    return null;
    """
    clicked = sb.execute_script(script)
    if clicked:
        print(f"    ✅ 最终兜底已点击: {clicked}")
        return clicked
    raise Exception("最终兜底仍未找到可点击的确认/支付按钮")


def dump_clickable_texts(sb, limit=30):
    """打印当前页面可点击按钮文本，便于定位网站改版后的按钮。"""
    try:
        items = sb.execute_script("""
        return Array.from(document.querySelectorAll('button,a,input[type=button],input[type=submit],.layui-layer-btn0,.layui-layer-btn a,.layui-layer-btn1,#payamount,.payamount,button.pay-now,.xfSubmit'))
          .map(el => (el.innerText || el.value || el.getAttribute('title') || el.id || el.className || '').trim())
          .filter(Boolean).slice(0, arguments[0]);
        """, limit)
        print(f"    🧭 当前可点击按钮/链接文本: {items}")
    except Exception as e:
        print(f"    ⚠️ 可点击文本提取失败: {e}")


def latest_screenshots(username, limit=1):
    safe_name = username.replace("@", "_").replace(".", "_")
    files = glob.glob(f"screenshots/{safe_name}_*.png")
    files.sort(key=os.path.getmtime, reverse=True)
    return files[:limit]


def send_tg_notify(username, status, message="", images=None, expire_text="", balance_text=""):
    bot_token = os.environ.get("BOT_TOKEN", "")
    chat_id = os.environ.get("CHAT_ID", "")
    if not bot_token or not chat_id:
        print("    ⚠️ 未配置 BOT_TOKEN/CHAT_ID，跳过 TG 通知。")
        return
    if requests is None:
        print("    ⚠️ requests 未安装，跳过 TG 通知。")
        return

    text = f"📡 <b>NatFreeCloud 自动续约通知</b>\n👤 账号: <code>{escape(username)}</code>\n📌 状态: <b>{escape(status)}</b>"
    if expire_text:
        text += f"\n📅 续约后到期: <b>{escape(expire_text)}</b>"
    if balance_text:
        text += f"\n💰 续约后账户信息: {escape(balance_text)}"
    if message:
        text += f"\n📝 详情: {escape(message[:800])}"
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=15,
        )
        resp.raise_for_status()
        print("    ✅ TG 文字通知发送成功")
        # TG 只发送 1 张关键截图，避免连续刷屏。
        for img in (images or [])[:1]:
            if os.path.exists(img):
                with open(img, "rb") as f:
                    r = requests.post(
                        f"https://api.telegram.org/bot{bot_token}/sendPhoto",
                        data={"chat_id": chat_id, "caption": os.path.basename(img)},
                        files={"photo": f},
                        timeout=30,
                    )
                    r.raise_for_status()
                    print(f"    ✅ TG 截图发送成功: {img}")
    except Exception as e:
        print(f"    ❌ TG 通知发送失败: {e}")

# ==========================================
# 2. Cloudflare 绕过辅助函数 
# ==========================================
def is_cloudflare_interstitial(sb) -> bool:
    try:
        page_source = sb.get_page_source()
        title = sb.get_title().lower() if sb.get_title() else ""
        indicators = ["Just a moment", "Verify you are human", "Checking your browser", "Checking if the site connection is secure"]
        for ind in indicators:
            if ind in page_source:
                return True
        if "just a moment" in title or "attention required" in title:
            return True
        body_len = sb.execute_script('(function() { return document.body ? document.body.innerText.length : 0; })();')
        if body_len is not None and body_len < 200 and "challenges.cloudflare.com" in page_source:
            return True
        return False
    except:
        return False

def bypass_cloudflare_interstitial(sb, max_attempts=4) -> bool:
    print("    🛡️ 检测到 CF 5秒盾，准备破除...")
    for attempt in range(max_attempts):
        print(f"      ▶ 尝试绕过 ({attempt+1}/{max_attempts})...")
        try:
            sb.uc_gui_click_captcha()
            time.sleep(6)
            if not is_cloudflare_interstitial(sb):
                print("      ✅ CF 5秒盾已通过！")
                return True
        except Exception as e:
            pass
        time.sleep(3)
    return False

def handle_turnstile_verification(sb) -> bool:
    try:
        cookie_btn = 'button[data-cky-tag="accept-button"]'
        if sb.is_element_visible(cookie_btn):
            sb.click(cookie_btn)
            time.sleep(1)
    except:
        pass

    sb.execute_script('''
        try {
            var t = document.querySelector('.cf-turnstile') || 
                    document.querySelector('iframe[src*="challenges.cloudflare"]') || 
                    document.querySelector('iframe[src*="turnstile"]');
            if (t) t.scrollIntoView({behavior:'smooth', block:'center'});
        } catch(e) {}
    ''')
    time.sleep(2)

    has_turnstile = False
    for _ in range(15):
        if (sb.is_element_present('iframe[src*="challenges.cloudflare"]') or 
            sb.is_element_present('iframe[src*="turnstile"]') or 
            sb.is_element_present('.cf-turnstile') or 
            sb.is_element_present('input[name="cf-turnstile-response"]')):
            has_turnstile = True
            break
        time.sleep(1)

    if not has_turnstile:
        print("    🟢 无感验证通过 (未发现 Turnstile)")
        return True

    print("    🧩 发现验证码，执行拟人点击...")
    verified = False
    
    for attempt in range(1, 4):
        try:
            sb.uc_gui_click_captcha()
        except:
            pass
            
        for _ in range(10):
            if sb.is_element_present('input[name="cf-turnstile-response"]'):
                token = sb.get_attribute('input[name="cf-turnstile-response"]', 'value')
                if token and len(token) > 20:
                    print("      ✅ 物理点击成功，已获取 Token！")
                    verified = True
                    break
            time.sleep(1)
            
        if verified:
            break

    if not verified:
        for _ in range(30):
            if sb.is_element_present('input[name="cf-turnstile-response"]'):
                token = sb.get_attribute('input[name="cf-turnstile-response"]', 'value')
                if token and len(token) > 20:
                    print("      ✅ 验证码自动放行，已获取 Token！")
                    verified = True
                    break
            time.sleep(1)

    return verified

# ==========================================
# 3. 单个账号的处理流程
# ==========================================
def process_single_account(username, password):
    result = {
        "username": username,
        "login": "未开始",
        "sign_in": "未开始",
        "renew": "未执行",
        "expire": "",
        "balance": "",
        "reason": "",
    }
    print(f"\n==========================================")
    print(f"➡️ 开始处理账号: {username}")
    print(f"==========================================")
    
    env_proxy = os.environ.get("HTTP_PROXY")
    
    with SB(
        uc=True,            
        test=True,          
        locale="en",        
        headless=False,      
        proxy=env_proxy,    
        chromium_arg="--disable-blink-features=AutomationControlled,--window-size=1920,1080"
    ) as sb:
        print(f"🌐 正在访问目标网站: {CONFIG['target_url']}")
        sb.uc_open_with_reconnect(CONFIG['target_url'], reconnect_time=8)
        time.sleep(4)
        
        take_screenshot(sb, "01_初始访问页面", username)

        page_source = sb.get_page_source()
        if "Error 1005" in page_source or "Access denied" in page_source:
            print("🚨 致命错误：当前代理节点的 IP 被彻底封锁 (Error 1005)！")
            take_screenshot(sb, "Error_1005_节点被封锁", username)
            sys.exit(1)

        if is_cloudflare_interstitial(sb):
            if not bypass_cloudflare_interstitial(sb):
                return 
            time.sleep(3) 
            
        handle_turnstile_verification(sb)
        time.sleep(3)
        take_screenshot(sb, "2_准备填写表单", username)

        try:
            # --- 登录模块 ---
            login_success = False 
            
            for login_attempt in range(2):
                print(f"    ▶ 开始第 {login_attempt + 1} 次尝试登录...")
                
                # ==================================================
                # 🌟 优化：验证码最多尝试 10 次，失败则退出程序
                # ==================================================
                captcha_success = False # 设定一个标记，记录验证码是否成功获取
                
                for captcha_attempt in range(10): # 循环 10 次
                    sb.wait_for_element(CONFIG['captcha_img_selector'], timeout=10)
                    img_src = sb.get_attribute(CONFIG['captcha_img_selector'], "src")
                    
                    if img_src and "base64," in img_src:
                        base64_data = img_src.split(',')[1]
                        img_bytes = base64.b64decode(base64_data)
                        ocr = ddddocr.DdddOcr(show_ad=False)
                        captcha_text = ocr.classification(img_bytes)
                        
                        # 判断是否全部为数字
                        if captcha_text.isdigit():
                            print(f"      ✅ 验证码识别成功 (纯数字): {captcha_text}")
                            captcha_success = True # 将标记改为成功
                            break # 是纯数字，跳出这 10 次的循环，继续往下执行
                        else:
                            print(f"      ⚠️ 第 {captcha_attempt + 1} 次识别结果含字母/乱码 ({captcha_text})，点击刷新...")
                            sb.click(CONFIG['captcha_img_selector'])
                            time.sleep(2) # 等待两秒让新图片加载出来
                    else:
                        print("      ⚠️ 无法获取验证码图片。")
                        break
                
                # 检查标记：如果循环了 10 次还是没成功，执行退出操作
                if not captcha_success:
                    print("    🚨 致命错误：验证码连续 10 次识别失败！程序将直接退出。")
                    sys.exit(1) # 调用 sys.exit(1) 强制终止整个 Python 脚本
                # ==================================================

                sb.clear(CONFIG['username_selector'])
                sb.type(CONFIG['username_selector'], username)
                
                sb.clear(CONFIG['password_selector'])
                sb.type(CONFIG['password_selector'], password)
                
                sb.clear(CONFIG['captcha_input_selector'])
                sb.type(CONFIG['captcha_input_selector'], captcha_text)
                
                sb.click(CONFIG['login_btn_selector'])
                time.sleep(5)
                
                if sb.is_element_present(CONFIG['user_center_selector']):
                    login_success = True
                    print(f"    📄 登录验证成功！当前页面: {sb.get_title()}")
                    break 
                else:
                    print(f"    ⚠️ 第 {login_attempt + 1} 次登录似乎失败了（没找到用户中心），正在准备重试...")
                    sb.refresh() 
                    time.sleep(3)
            
            if not login_success:
                print("    ❌ 两次登录尝试均未成功，跳过当前账号的后续任务。")
                result["login"] = "失败"
                result["reason"] = "两次登录尝试均未成功"
                return result
            result["login"] = "成功"

            # ==========================================
            # 🌟 每日签到与积分提取模块
            # ==========================================
            print("\n>>> 🎁 准备执行每日签到任务...")
            sb.open(CONFIG['sign_in_url'])
            time.sleep(4) 
            
            balance_value = 0.0 
            
            max_retries = 5
            for attempt in range(max_retries):
                sb.click(CONFIG['sign_in_btn_selector'])
                time.sleep(2) 
                
                question_text = sb.get_text(CONFIG['math_question_selector'])
                math_expr = question_text.replace("请计算：", "").replace("=", "").strip()
                result = eval(math_expr)
                
                if isinstance(result, float) and not result.is_integer():
                    sb.refresh() 
                    time.sleep(3)
                    continue     
                
                final_answer = int(result) 
                print(f"    ✅ 计算结果为整数: {final_answer}，正在提交...")
                
                sb.clear(CONFIG['math_input_selector']) 
                sb.type(CONFIG['math_input_selector'], str(final_answer))
                
                sb.click(CONFIG['verify_btn_selector'])
                
                sb.wait_for_element(CONFIG['popup_content_selector'], timeout=5)
                popup_msg = sb.get_text(CONFIG['popup_content_selector'])
                print(f"    🔔 签到系统提示: 【{popup_msg}】")
                
                sb.click(CONFIG['popup_confirm_btn_selector'])
                time.sleep(2) 
                
                print("    🔄 正在强制刷新页面以同步最新的余额数据...")
                sb.refresh()
                time.sleep(4)
                
                try:
                    balance_text = sb.get_text(CONFIG['points_balance_selector'])
                    print(f"    💰 当前账户原始信息: {balance_text}")
                    match = re.search(r"(\d+(?:\.\d+)?)", balance_text)
                    if match:
                        balance_value = float(match.group(1))
                        print(f"    🔍 提取并转换可用积分为: {balance_value}")
                except Exception:
                    print("    ⚠️ 无法获取积分余额。")

                result["sign_in"] = "成功"
                result["balance"] = balance_text if 'balance_text' in locals() else str(balance_value)
                print("    🎉 签到流程结束。\n")
                break 
            else:
                print("    ❌ 签到失败：连续 5 次刷新都没有遇到可以整除的算术题。")
                result["sign_in"] = "失败"
                result["reason"] = "连续 5 次没有遇到可整除算术题"

            # ==========================================
            # 🌟 积分判断与云服务器续费模块
            # ==========================================
            if balance_value >= 0.01:
                print(f">>> 💻 积分达标 (当前 {balance_value})，开始执行云服务器续费任务...")
                
                print("    ▶ 正在强制跳转至云服务器列表网址...")
                sb.open(CONFIG['server_list_url'])
                time.sleep(4) 
                take_screenshot(sb, "8_云服务器列表页", username)
                
                if sb.is_element_present(CONFIG['server_checkbox_selector']):
                    sb.click(CONFIG['server_checkbox_selector'])
                    print("    ▶ 已勾选目标云服务器。")
                    
                    sb.js_click(CONFIG['list_renew_btn_selector'])
                    time.sleep(4) 
                    
                    print("    ▶ 正在生成续费订单...")
                    take_screenshot(sb, "9_点击续费后等待确认按钮", username)
                    dump_clickable_texts(sb)
                    try:
                        click_first_available(sb, [
                            CONFIG['confirm_renew_btn_selector'],
                            '.layui-layer-btn0',
                            '.layui-layer-btn a',
                            'button[type="submit"]',
                            '//*[contains(normalize-space(.), "确认续费")]',
                            '//*[contains(normalize-space(.), "生成订单")]',
                            '//*[contains(normalize-space(.), "确认")]',
                            '//*[contains(normalize-space(.), "提交")]',
                        ], timeout=5)
                    except Exception:
                        click_by_text(sb, ["确认续费", "生成订单", "确认", "提交", "立即续费"])
                    time.sleep(5)
                    take_screenshot(sb, "10_确认续费后支付页面", username)
                    dump_clickable_texts(sb)
                    
                    print("    ▶ 已调起支付面板，等待确认...")
                    try:
                        click_first_available(sb, [
                            CONFIG['order_pay_btn_selector'],
                            '#payamount',
                            '.payamount',
                            'button[type="submit"]',
                            '//*[contains(normalize-space(.), "余额支付")]',
                            '//*[contains(normalize-space(.), "立即支付")]',
                            '//*[contains(normalize-space(.), "支付")]',
                        ], timeout=8)
                    except Exception:
                        click_by_text(sb, ["余额支付", "立即支付", "支付", "确认支付"])
                    time.sleep(2)
                    take_screenshot(sb, "11_支付确认弹窗", username)
                    dump_clickable_texts(sb)
                    
                    try:
                        click_first_available(sb, [
                            CONFIG['modal_pay_btn_selector'],
                            '.layui-layer-btn0',
                            '.layui-layer-btn a',
                            '.layui-layer-btn1',
                            'button.pay-now',
                            'button[type="submit"]',
                            'input[type="submit"]',
                            '//*[contains(normalize-space(.), "确认支付")]',
                            '//*[contains(normalize-space(.), "确认付款")]',
                            '//*[contains(normalize-space(.), "余额支付")]',
                            '//*[contains(normalize-space(.), "立即支付")]',
                            '//*[contains(normalize-space(.), "确定")]',
                            '//*[contains(normalize-space(.), "确认")]',
                            '//*[contains(normalize-space(.), "支付")]',
                        ], timeout=8)
                    except Exception:
                        try:
                            click_by_text(sb, ["确认支付", "确认付款", "余额支付", "立即支付", "支付", "确认", "确定", "提交"])
                        except Exception:
                            click_last_submit_or_confirm(sb)
                    print("    ▶ 💸 已确认支付，正在等待系统处理并跳转...")
                    
                    time.sleep(8) 
                    renew_result_screenshot = take_screenshot(sb, "12_支付完成跳转详情页", username)
                    expire_text = "未提取到到期时间，请查看截图确认"
                    expire_date = ""
                    
                    try:
                        p_elements = sb.find_elements('section.text-gray p')
                        for p in p_elements:
                            if "到期时间" in p.text:
                                expire_text = p.text.strip()
                                match = re.search(r"\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}(?::\d{2})?)?", expire_text)
                                expire_date = match.group(0) if match else expire_text.replace("到期时间", "").replace("：", "").replace(":", "").strip()
                                print(f"    📅 续费成功！最新 {expire_text}")
                                break
                    except Exception as e:
                        print(f"    ⚠️ 到期时间提取失败: {e}")
                    
                    print("\n>>> 🔄 续费完成，返回签到中心查看最新积分...")
                    sb.open(CONFIG['sign_in_url'])
                    time.sleep(4)
                    take_screenshot(sb, "13_续费后返回签到中心", username)
                    
                    try:
                        final_balance_text = sb.get_text(CONFIG['points_balance_selector'])
                        print(f"    💰 续费后账户最新信息: {final_balance_text}")
                        match = re.search(r"(\d+(?:\.\d+)?)", final_balance_text)
                        if match:
                            print(f"    ✨ 最终剩余可用积分: {float(match.group(1))}")
                    except Exception:
                        final_balance_text = "无法获取最终积分余额"
                        print("    ⚠️ 无法获取最终积分余额。")

                    product_list_screenshot = None
                    try:
                        print("\n>>> 📋 正在打开云服务器列表，截取产品与到期时间区域...")
                        sb.open(CONFIG['server_list_url'])
                        time.sleep(4)
                        sb.execute_script("""
                            const table = document.querySelector('table') || document.querySelector('.table') || document.querySelector('.layui-table');
                            if (table) table.scrollIntoView({block: 'center'});
                        """)
                        time.sleep(1)
                        product_list_screenshot = take_screenshot(sb, "14_续费后云服务器产品列表", username)
                    except Exception as e:
                        print(f"    ⚠️ 产品列表截图失败: {e}")

                    success_image = [product_list_screenshot or renew_result_screenshot] if (product_list_screenshot or renew_result_screenshot) else latest_screenshots(username)
                    result["renew"] = "成功"
                    result["expire"] = expire_date or expire_text
                    result["balance"] = final_balance_text
                    send_tg_notify(
                        username,
                        "✅ 续约流程已完成",
                        "",
                        success_image,
                        expire_date or expire_text,
                        final_balance_text,
                    )
                        
                else:
                    msg = "当前账号下未检测到可续费的云服务器，已跳过。"
                    print(f"    ⚠️ {msg}")
                    result["renew"] = "跳过"
                    result["reason"] = msg
                    send_tg_notify(username, "⚠️ 未检测到可续费服务器", msg, latest_screenshots(username))
            else:
                msg = f"积分不足 (当前 {balance_value} < 0.01)，安全退出当前账号的后续操作！"
                print(f">>> 🛑 {msg}")
                result["renew"] = "跳过"
                result["reason"] = msg
                send_tg_notify(username, "🛑 积分不足未续约", msg, latest_screenshots(username))

        except Exception as e:
            print(f"    ❌ 账号处理或执行过程中出现错误: {e}")
            result["reason"] = str(e)
            if result["renew"] == "未执行":
                result["renew"] = "异常"
            take_screenshot(sb, "Error_程序崩溃截图", username)
            send_tg_notify(username, "❌ 续约流程异常", str(e), latest_screenshots(username))

    return result

# ==========================================
# 4. 主程序入口
# ==========================================
def collect_accounts():
    """Collect accounts from env vars.

    Supported formats:
    - acount / ACOUNT: email:password[,email2:password2]
    - ACOUNT_2, ACOUNT_3...: email:password
    - ACCOUNTS: newline or comma separated email:password entries
    """
    raw_items = []

    for key in ("acount", "ACOUNT", "ACCOUNTS"):
        value = os.environ.get(key, "").strip()
        if value:
            raw_items.extend(re.split(r"[\n,]+", value))

    for i in range(2, 21):
        value = os.environ.get(f"ACOUNT_{i}", "").strip()
        if value:
            raw_items.append(value)

    accounts = []
    seen = set()
    for item in raw_items:
        item = item.strip()
        if not item or ':' not in item:
            continue
        username, password = item.split(':', 1)
        username = username.strip()
        password = password.strip()
        if not username or not password or username in seen:
            continue
        seen.add(username)
        accounts.append((username, password))
    return accounts


def send_summary_notify(results):
    if not results:
        return
    lines = ["📊 <b>NatFreeCloud 多账号执行汇总</b>"]
    for item in results:
        lines.append(
            "\n".join([
                f"👤 <code>{escape(item.get('username', ''))}</code>",
                f"🔐 登录: {escape(item.get('login', ''))}",
                f"🎁 签到: {escape(item.get('sign_in', ''))}",
                f"🔄 续约: {escape(item.get('renew', ''))}",
                f"📅 到期: {escape(item.get('expire') or '-')}",
                f"💰 余额: {escape(item.get('balance') or '-')}",
                f"📝 原因: {escape(item.get('reason') or '-')}",
            ])
        )
    send_tg_notify("SYSTEM", "📊 多账号执行汇总", "\n\n".join(lines))


def main():
    print("🚀 自动化任务启动...")
    accounts = collect_accounts()

    if not accounts:
        print("⚠️ 未获取到账户环境变量！请配置 acount/ACOUNT、ACOUNT_2 或 ACCOUNTS。")
        return

    print(f"📋 共检测到 {len(accounts)} 个账号。")

    results = []
    for username, password in accounts:
        results.append(process_single_account(username, password))

    send_summary_notify(results)
    print("\n🏁 所有队列任务已全部执行完成！")

if __name__ == "__main__":
    main()
