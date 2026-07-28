import json
import os
import datetime
import time
import traceback
import threading
import requests
from flask import Flask, request, jsonify, render_template

# ---------- 目录配置 ----------
DATA_DIR = "data"
CONFIG_FILE = os.path.join(DATA_DIR, "cookies.json")
LAST_SIGN_FILE = os.path.join(DATA_DIR, "last_sign_date.txt")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
SETTING_FILE = os.path.join(DATA_DIR, "setting.json")

# ---------- 固定参数 ----------
HEARTBEAT_URL = "https://xueba.asus.com.cn/3ea5551da13d4234af1aa34a919c34d6/sxb/api/User/access"
SIGNIN_URL = "https://xueba.asus.com.cn/3ea5551da13d4234af1aa34a919c34d6/sxb/api/SignIn/submit"
MONTH_LIST_URL = "https://xueba.asus.com.cn/3ea5551da13d4234af1aa34a919c34d6/sxb/api/SignIn/monthList"

# ---------- 默认 Cookie ----------
DEFAULT_COOKIES = {
    "csrftoken": "yHA7oyLobMp8m1JgnfR5TidCo8aapJFs1gAlxMjaoicmnT4GU8ZH8sTz3q3xD0N3",
    "acw_tc": "2f66178217852487381362968e068cf46dbd39eff5fe9f3795029912656400",
    "sessionid": "2p8wgx1uo55sdo62sdi70vdmkk98qzvq"
}

# ---------- 请求头模板 ----------
BASE_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Connection": "keep-alive",
    "Content-Type": "application/json",
    "Origin": "https://xueba.asus.com.cn",
    "Referer": "https://xueba.asus.com.cn/3ea5551da13d4234af1aa34a919c34d6/sxb/?s=*oeTY20mm_emJatKWvGQZ8I1goeTI&b=1",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 QQBrowser/21.5.9239.400",
    "X-Requested-With": "XMLHttpRequest",
    "sec-ch-ua": '"Not)A;Brand";v="8", "Chromium";v="138"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

# ---------- Flask 应用 ----------
app = Flask(__name__)

# ---------- 全局变量 ----------
session = None
history_lock = threading.Lock()
setting_lock = threading.Lock()

# ==================== 工具函数 ====================
def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def ensure_default_cookie_file():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_COOKIES, f, indent=2, ensure_ascii=False)

def ensure_default_setting_file():
    if not os.path.exists(SETTING_FILE):
        with open(SETTING_FILE, "w", encoding="utf-8") as f:
            json.dump({"sign_time": "05:00"}, f, indent=2)

def load_cookies() -> dict:
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, IOError):
        return DEFAULT_COOKIES.copy()

def save_cookies(cookies: dict) -> bool:
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False

def load_setting() -> dict:
    try:
        with open(SETTING_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"sign_time": "05:00"}

def save_setting(setting: dict) -> bool:
    try:
        with open(SETTING_FILE, "w", encoding="utf-8") as f:
            json.dump(setting, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False

def get_sign_time() -> str:
    with setting_lock:
        setting = load_setting()
        return setting.get("sign_time", "05:00")

def load_last_sign_date() -> str | None:
    try:
        if os.path.exists(LAST_SIGN_FILE):
            with open(LAST_SIGN_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception:
        pass
    return None

def save_last_sign_date(date_str: str) -> bool:
    try:
        with open(LAST_SIGN_FILE, "w", encoding="utf-8") as f:
            f.write(date_str)
        return True
    except Exception:
        return False

def load_history() -> dict:
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_history(history: dict):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

def record_sign_result(date_str: str, status: str):
    with history_lock:
        hist = load_history()
        hist[date_str] = status
        save_history(hist)

def get_platform_dates(year: int, month: int) -> list:
    dt = datetime.datetime(year, month, 1, 0, 0, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
    timestamp_ms = int(dt.timestamp() * 1000)
    url = f"{MONTH_LIST_URL}?_T={int(time.time()*1000)}&date={timestamp_ms}"
    try:
        resp = session.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get('success') and 'data' in data and 'dates' in data['data']:
            dates = data['data']['dates']
            result = []
            for ts in dates:
                d = datetime.datetime.fromtimestamp(ts/1000, tz=datetime.timezone(datetime.timedelta(hours=8)))
                result.append(d.strftime("%Y-%m-%d"))
            return result
    except Exception as e:
        print(f"[平台] 获取签到记录失败: {e}", flush=True)
    return []

def create_session() -> requests.Session:
    sess = requests.Session()
    cookies = load_cookies()
    sess.cookies.update(cookies)
    sess.headers.update(BASE_HEADERS)
    sess.headers['X-CSRFTOKEN'] = cookies.get('csrftoken', '')
    return sess

def refresh_csrf_token(sess: requests.Session) -> None:
    token = sess.cookies.get('csrftoken', '')
    sess.headers['X-CSRFTOKEN'] = token

def do_heartbeat(sess: requests.Session) -> bool:
    old_cookies = sess.cookies.get_dict()
    refresh_csrf_token(sess)
    try:
        resp = sess.post(HEARTBEAT_URL, data="{}", timeout=10)
        resp.raise_for_status()
    except Exception:
        return False
    new_cookies = sess.cookies.get_dict()
    if new_cookies != old_cookies:
        save_cookies(new_cookies)
    return True

def do_signin(sess: requests.Session) -> tuple[bool, str]:
    refresh_csrf_token(sess)
    try:
        resp = sess.post(SIGNIN_URL, data="{}", timeout=10)
        resp.raise_for_status()
    except Exception as e:
        return False, f"网络请求失败: {e}"

    save_cookies(sess.cookies.get_dict())

    try:
        data = resp.json()
    except json.JSONDecodeError as e:
        return False, f"响应格式错误: {e}"

    if data.get('success') is True:
        msg = data.get('data', {}).get('message', '')
        record_sign_result(datetime.date.today().isoformat(), "success")
        return True, msg
    else:
        msg = data.get('msg', '')
        if '今日您已签到' in msg:
            record_sign_result(datetime.date.today().isoformat(), "success")
            return True, msg
        record_sign_result(datetime.date.today().isoformat(), "failed")
        return False, msg

def should_sign_today() -> bool:
    today = datetime.date.today().isoformat()
    last = load_last_sign_date()
    return last == today

def mark_signed_today() -> None:
    today = datetime.date.today().isoformat()
    save_last_sign_date(today)

def is_time_to_sign(target_time: str) -> bool:
    now = datetime.datetime.now()
    try:
        target_hour, target_min = map(int, target_time.split(':'))
        return now.hour > target_hour or (now.hour == target_hour and now.minute >= target_min)
    except:
        return False

def background_worker(sess: requests.Session):
    print(f"[系统] 后台签到线程已启动", flush=True)
    while True:
        try:
            do_heartbeat(sess)
            sign_time = get_sign_time()
            if not should_sign_today() and is_time_to_sign(sign_time):
                completed, msg = do_signin(sess)
                if completed:
                    mark_signed_today()
                    print(f"[签到] {msg}", flush=True)
                else:
                    print(f"[签到] 失败: {msg}", flush=True)
            time.sleep(60)
        except KeyboardInterrupt:
            print("[系统] 后台线程收到停止信号", flush=True)
            break
        except Exception as e:
            print(f"[严重错误] 后台循环异常: {e}", flush=True)
            traceback.print_exc()
            time.sleep(60)

# ==================== Flask 路由 ====================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/history')
def get_history():
    with history_lock:
        return jsonify(load_history())

@app.route('/platform_history')
def platform_history():
    month = request.args.get('month', '')
    try:
        year, month = map(int, month.split('-'))
    except:
        return jsonify({"dates": []})
    dates = get_platform_dates(year, month)
    return jsonify({"dates": dates})

@app.route('/cookies', methods=['POST'])
def update_cookies():
    new_cookies = request.get_json()
    if not isinstance(new_cookies, dict):
        return jsonify({"status": "error", "msg": "需要 JSON 对象"}), 400
    if save_cookies(new_cookies):
        global session
        if session:
            session.cookies.clear()
            session.cookies.update(new_cookies)
            refresh_csrf_token(session)
        return jsonify({"status": "ok", "msg": "Cookies 更新成功"})
    else:
        return jsonify({"status": "error", "msg": "写入文件失败"}), 500

@app.route('/setting', methods=['GET', 'POST'])
def setting():
    if request.method == 'GET':
        with setting_lock:
            return jsonify(load_setting())
    else:
        data = request.get_json()
        if not data or 'sign_time' not in data:
            return jsonify({"status": "error", "msg": "缺少 sign_time"}), 400
        sign_time = data['sign_time']
        try:
            datetime.datetime.strptime(sign_time, "%H:%M")
        except:
            return jsonify({"status": "error", "msg": "时间格式错误，请使用 HH:MM"}), 400
        with setting_lock:
            setting = load_setting()
            setting['sign_time'] = sign_time
            if save_setting(setting):
                return jsonify({"status": "ok", "msg": "签到时间已更新"})
            else:
                return jsonify({"status": "error", "msg": "写入设置文件失败"}), 500

# ==================== 主程序入口 ====================
def main():
    global session
    ensure_data_dir()
    ensure_default_cookie_file()
    ensure_default_setting_file()
    session = create_session()
    worker = threading.Thread(target=background_worker, args=(session,), daemon=True)
    worker.start()
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.run(host='0.0.0.0', port=23344, debug=True)

if __name__ == "__main__":
    main()
