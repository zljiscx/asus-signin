let currentDate = new Date();

function loadAllHistories(year, month) {
    const localPromise = fetch('/history').then(r => r.json());
    const monthStr = String(year) + '-' + String(month).padStart(2,'0');
    const platformPromise = fetch(`/platform_history?month=${monthStr}`).then(r => r.json());
    return Promise.all([localPromise, platformPromise]).then(([local, platform]) => {
        return { local, platform: platform.dates || [] };
    });
}

function renderCalendar(histories) {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const now = new Date();
    const today = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;

    const monthNames = ['一月','二月','三月','四月','五月','六月','七月','八月','九月','十月','十一月','十二月'];
    document.getElementById('monthLabel').textContent = `${year}年 ${monthNames[month]}`;

    const container = document.getElementById('calendar');
    container.innerHTML = '';

    const weekDays = ['日','一','二','三','四','五','六'];
    weekDays.forEach(d => {
        const div = document.createElement('div');
        div.className = 'day header';
        div.textContent = d;
        container.appendChild(div);
    });

    for (let i = 0; i < firstDay; i++) {
        const div = document.createElement('div');
        div.className = 'day empty';
        container.appendChild(div);
    }

    for (let day = 1; day <= daysInMonth; day++) {
        const dateStr = `${year}-${String(month+1).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
        const div = document.createElement('div');
        div.className = 'day';
        div.textContent = day;

        if (dateStr === today) {
            div.classList.add('today');
        }
        const localStatus = histories.local[dateStr];
        const platformHas = histories.platform.includes(dateStr);

        if (localStatus === 'success' && platformHas) {
            div.classList.add('both');
        } else if (localStatus === 'success') {
            div.classList.add('success');
        } else if (platformHas) {
            div.classList.add('platform');
        } else {
            div.style.background = '#f0f0f0';
        }
        container.appendChild(div);
    }
}

function refreshCalendar() {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth() + 1;
    loadAllHistories(year, month).then(histories => {
        renderCalendar(histories);
    }).catch(err => {
        console.error('加载数据失败', err);
    });
}

document.getElementById('prevMonth').addEventListener('click', () => {
    currentDate.setMonth(currentDate.getMonth() - 1);
    refreshCalendar();
});
document.getElementById('nextMonth').addEventListener('click', () => {
    currentDate.setMonth(currentDate.getMonth() + 1);
    refreshCalendar();
});
document.getElementById('todayMonth').addEventListener('click', () => {
    currentDate = new Date();
    refreshCalendar();
});

function loadSetting() {
    fetch('/setting').then(r => r.json()).then(data => {
        if (data.sign_time) {
            document.getElementById('signTime').value = data.sign_time;
        }
        if (data.wecom_webhook_key) {
            document.getElementById('webhookKey').value = data.wecom_webhook_key;
        }
    }).catch(e => console.error('加载设置失败', e));
}

document.getElementById('saveSettingBtn').addEventListener('click', () => {
    const time = document.getElementById('signTime').value;
    if (!time) {
        document.getElementById('settingMsg').textContent = '请选择有效时间';
        return;
    }
    fetch('/setting', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({sign_time: time})
    }).then(r => r.json()).then(data => {
        document.getElementById('settingMsg').textContent = data.msg || '设置已保存';
        if (data.status === 'ok') {
            document.getElementById('settingMsg').style.color = 'green';
        } else {
            document.getElementById('settingMsg').style.color = 'red';
        }
    }).catch(e => {
        document.getElementById('settingMsg').textContent = '保存失败: ' + e;
    });
});

document.getElementById('submitCookieBtn').addEventListener('click', () => {
    const val = document.getElementById('cookieInput').value.trim();
    if (!val) {
        document.getElementById('msg').textContent = '请输入 Cookies';
        return;
    }
    let cookiesObj = null;
    try {
        cookiesObj = JSON.parse(val);
    } catch(e) {
        const pairs = val.split(';').map(s => s.trim()).filter(s => s);
        const obj = {};
        for (let pair of pairs) {
            const eq = pair.indexOf('=');
            if (eq > 0) {
                const key = pair.substring(0, eq).trim();
                const value = pair.substring(eq+1).trim();
                obj[key] = value;
            }
        }
        if (Object.keys(obj).length > 0) {
            cookiesObj = obj;
        } else {
            document.getElementById('msg').textContent = '❌ 无法解析 Cookies 格式';
            return;
        }
    }
    fetch('/cookies', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(cookiesObj)
    }).then(res => res.json()).then(data => {
        document.getElementById('msg').textContent = data.msg || (data.status === 'ok' ? '✅ 更新成功' : '❌ 更新失败');
        if (data.status === 'ok') {
            refreshCalendar();
        }
    }).catch(err => {
        document.getElementById('msg').textContent = '❌ 请求失败: ' + err;
    });
});

document.getElementById('saveWebhookBtn').addEventListener('click', () => {
    const key = document.getElementById('webhookKey').value.trim();
    // 如果 key 为空，弹出确认框
    if (!key) {
        if (!confirm('⚠️ 确认要清空 Webhook Key 吗？\n清空后将不会推送任何消息。')) {
            return; // 取消则不提交
        }
    }
    // 简单验证：只允许字母、数字、连字符（UUID格式）
    if (key && !/^[a-f0-9\-]+$/i.test(key)) {
        document.getElementById('webhookMsg').textContent = '⚠️ Key 格式不正确（应为字母数字和连字符）';
        document.getElementById('webhookMsg').style.color = 'red';
        return;
    }
    fetch('/setting', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ wecom_webhook_key: key })
    }).then(r => r.json()).then(data => {
        document.getElementById('webhookMsg').textContent = data.msg || '已保存';
        document.getElementById('webhookMsg').style.color = data.status === 'ok' ? 'green' : 'red';
    }).catch(e => {
        document.getElementById('webhookMsg').textContent = '保存失败: ' + e;
        document.getElementById('webhookMsg').style.color = 'red';
    });
});

loadSetting();
refreshCalendar();
