from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
import subprocess
import functools
import os
import shlex
import mss
import io
import time
import threading
import requests
import telebot
from PIL import Image

app = Flask(__name__)
app.secret_key = 'YOUR_SECRET_KEY'

PASSWORD = "YOUR_PASSWORD_FOR_TERMINAL"
IS_WINDOWS = os.name == 'nt'
CONSOLE_ENCODING = 'cp866' if IS_WINDOWS else 'utf-8'
TG_TOKEN = "TELEGRAM_TOKEN"

bot = telebot.TeleBot(TG_TOKEN)

def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function

def get_public_ip():
    try:
        response = requests.get('https://api.ipify.org?format=json')
        return response.json()['ip']
    except Exception:
        return "Unknown IP"

@bot.message_handler(commands=['ip', 'start'])
def send_ip_info(message):
    ip = get_public_ip()
    link = f"http://{ip}:5000"
    text = f"🖥 **Server Online**\n🌐 IP: `{ip}`\n🔗 {link}\n🔑 `{PASSWORD}`"
    bot.reply_to(message, text, parse_mode='Markdown')



def start_bot():
    try:
        bot.polling(non_stop=True)
    except:
        pass

def gen_frames():
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        while True:
            start_time = time.time()
            frame_data = None
            try:
                img = sct.grab(monitor)
                img_pil = Image.frombytes('RGB', img.size, img.bgra, 'raw', 'BGRX')
                buf = io.BytesIO()
                img_pil.save(buf, format='JPEG', quality=40)
                frame_data = buf.getvalue()
            except Exception:
                time.sleep(0.1)
                continue
            if frame_data:
                try:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')
                except GeneratorExit:
                    break
                except Exception:
                    break
            elapsed = time.time() - start_time
            time.sleep(max(0, (1.0 / 15.0) - elapsed))


@app.route('/favicon.ico')
def favicon():
    return "", 204
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('dashboard', mode='cmd'))
        else:
            flash('Access Denied')
    return render_template('login.html')



@app.route('/dashboard/<mode>', methods=['GET', 'POST'])
@login_required
def dashboard(mode):
    if mode not in ['cmd', 'powershell', 'screen']:
        return redirect(url_for('dashboard', mode='cmd'))
    output = ""
    current_cmd = ""
    if request.method == 'POST':
        if 'command' in request.form:
            cmd_input = request.form.get('command', '').strip()
            current_cmd = cmd_input
            if cmd_input:
                try:
                    shell_mode = False
                    if mode == 'powershell':
                        args = ["powershell", "-Command", cmd_input]
                    else:
                        args = shlex.split(cmd_input)
                        if IS_WINDOWS and args[0].lower() in ['dir', 'del', 'copy', 'type', 'mkdir', 'echo']:
                            args = ["cmd", "/c"] + args
                    result = subprocess.run(args, capture_output=True, text=False, shell=shell_mode)
                    raw = result.stdout + result.stderr
                    try:
                        output = raw.decode(CONSOLE_ENCODING)
                    except:
                        output = raw.decode('cp1251', errors='replace')
                except Exception as e:
                    output = str(e)


    return render_template('dashboard.html',
                           output=output,
                           last_cmd=current_cmd,
                           mode=mode)




@app.route('/video_feed')
@login_required
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')
@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))


if __name__ == '__main__':
    t = threading.Thread(target=start_bot)
    t.daemon = True
    t.start()
    app.run(host='0.0.0.0', port=5500, debug=False, threaded=True)