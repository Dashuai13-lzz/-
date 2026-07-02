import requests
import subprocess
import os
import time
import json
import socket
import win32gui
import win32process

#pyinstaller -F zjy.py
def is_port_in_use(port):
    """检测端口是否被占用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.settimeout(1)
            result = s.connect_ex(('127.0.0.1', port))
            return result == 0
        except:
            return False


def find_edge_window():
    """查找 Edge 浏览器窗口"""
    edge_windows = []
    
    def callback(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd):
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                # 检查窗口标题是否包含 Edge 相关关键词
                title = win32gui.GetWindowText(hwnd)
                if title and ('Edge' in title or 'Microsoft Edge' in title or '新建标签页' in title or '学习' in title or '超星' in title):
                    edge_windows.append((hwnd, title, pid))
            except:
                pass
        return True
    
    win32gui.EnumWindows(callback, None)
    return edge_windows


class ChaoxingAutoPlayer:
    def __init__(self):
        self.debug_port = 9222
        self.base_url = f'http://127.0.0.1:{self.debug_port}'
        self.edge_process = None
    
    def start_edge(self):
        """启动 Edge 浏览器并启用远程调试"""
        # 先检测是否有 Edge 窗口
        edge_windows = find_edge_window()
        if edge_windows:
            print(f'检测到 {len(edge_windows)} 个 Edge 窗口')
            # 如果有窗口，尝试连接调试端口
            if is_port_in_use(self.debug_port):
                print(f'检测到调试端口 {self.debug_port} 已被占用，尝试连接...')
                if self.check_browser():
                    print('成功连接到已运行的浏览器')
                    return True
            print('有窗口但无法连接调试端口')
        
        # 没有窗口或连接失败，启动新的浏览器
        print('未检测到 Edge 窗口，启动新的浏览器...')
        
        edge_paths = [
            r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
            r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
            os.path.expandvars(r'%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe'),
        ]
        
        edge_exe = None
        for path in edge_paths:
            if os.path.exists(path):
                edge_exe = path
                print(f'找到 Edge: {path}')
                break
        
        if not edge_exe:
            raise FileNotFoundError('未找到 Edge 浏览器')
        
        # 确保调试目录存在
        debug_dir = 'C:\\Temp\\EdgeDebug'
        os.makedirs(debug_dir, exist_ok=True)
        
        cmd = [
            edge_exe,
            f'--remote-debugging-port={self.debug_port}',
            f'--user-data-dir={debug_dir}',
            '--no-first-run',
            '--no-default-browser-check',
            '--remote-allow-origins=*',
            '--disable-background-networking',
            '--disable-sync'
        ]
        
        print(f'启动命令：{" ".join(cmd)}')
        
        # 使用 start 命令启动浏览器（确保窗口出现）
        startup_cmd = 'start "" "' + '" "'.join(cmd) + '"'
        print(f'执行：{startup_cmd}')
        subprocess.Popen(startup_cmd, shell=True)
        
        # 等待浏览器启动
        print('等待浏览器启动...')
        for i in range(20):
            time.sleep(1)
            if self.check_browser():
                print(f'浏览器已启动，端口：{self.debug_port}')
                # 验证是否有窗口
                edge_windows = find_edge_window()
                if edge_windows:
                    print(f'检测到 {len(edge_windows)} 个 Edge 窗口')
                    return True
                print('调试端口可用但没有窗口，继续等待...')
            if i % 5 == 0 and i > 0:
                print(f'等待中... ({i}/20)')
        
        # 启动失败，尝试直接连接
        print('启动超时，尝试直接连接...')
        if self.check_browser():
            print('连接成功')
            return True
        
        return False
    
    def check_browser(self):
        """检查浏览器是否可用"""
        try:
            resp = requests.get(f'{self.base_url}/json', timeout=3)
            if resp.status_code == 200:
                return True
        except:
            return False
        return False
    
    def get_tabs(self):
        """获取所有标签页"""
        try:
            resp = requests.get(f'{self.base_url}/json', timeout=5)
            if resp.status_code != 200:
                return []
            
            all_tabs = resp.json()
            
            filtered_tabs = []
            for tab in all_tabs:
                url = tab.get('url', '')
                title = tab.get('title', '')
                type_ = tab.get('type', '')
                
                # 只过滤掉扩展和服务相关的标签页
                if not url:
                    continue
                if url.startswith('chrome-extension://'):
                    continue
                if 'Service Worker' in title:
                    continue
                if url == 'chrome://newtab/':
                    continue
                    
                filtered_tabs.append(tab)
            
            return filtered_tabs
        except Exception as e:
            return []
    
    def execute_js(self, tab_id, js_code):
        """使用 WebSocket 执行 JS"""
        try:
            import websocket
            
            # 获取所有标签页信息，找到对应的 WebSocket URL
            resp = requests.get(f'{self.base_url}/json', timeout=5)
            if resp.status_code != 200:
                print(f'获取标签页列表失败：{resp.status_code}')
                return None
            
            all_tabs = resp.json()
            ws_url = None
            for tab in all_tabs:
                if tab.get('id') == tab_id:
                    ws_url = tab.get('webSocketDebuggerUrl', '')
                    break
            
            if not ws_url:
                print(f'未找到标签页 {tab_id} 的 WebSocket URL')
                return None
            
            print(f'WebSocket URL: {ws_url}')
            
            # 连接 WebSocket
            ws = websocket.create_connection(ws_url, timeout=10)
            ws.settimeout(10)
            
            # 发送 Runtime.enable
            enable_cmd = {
                'id': 1,
                'method': 'Runtime.enable'
            }
            ws.send(json.dumps(enable_cmd))
            
            # 等待 Runtime.enable 响应
            try:
                msg = ws.recv()
                print(f'Runtime.enable 响应：{msg[:100]}')
            except:
                pass
            
            # 发送 Runtime.evaluate
            eval_cmd = {
                'id': 2,
                'method': 'Runtime.evaluate',
                'params': {
                    'expression': js_code,
                    'returnByValue': True,
                    'awaitPromise': True
                }
            }
            ws.send(json.dumps(eval_cmd))
            print('已发送 JS 执行请求')
            
            # 接收所有消息直到找到我们的 JS 执行结果
            import time
            start_time = time.time()
            received_count = 0
            while time.time() - start_time < 5:
                try:
                    msg = ws.recv()
                    received_count += 1
                    data = json.loads(msg)
                    print(f'收到消息 #{received_count}: id={data.get("id")}, method={data.get("method")}')
                    
                    # 查找我们的 JS 执行结果（id=2 的响应）
                    if data.get('id') == 2:
                        print(f'找到执行结果：{str(msg)[:200]}')
                        ws.close()
                        if 'result' in data:
                            value = data['result'].get('result', {}).get('value')
                            print(f'返回值：{value}')
                            return value
                        else:
                            print(f'结果格式异常：{data}')
                        return None
                except websocket.WebSocketTimeoutException:
                    print('等待超时')
                    break
                except Exception as e:
                    print(f'接收消息出错：{e}')
                    break
            
            print(f'未找到 JS 执行结果，共收到 {received_count} 条消息')
            ws.close()
            return None
        except Exception as e:
            print(f'WebSocket 执行失败：{e}')
            import traceback
            traceback.print_exc()
            return None
    
    def get_video_info(self, tab_id):
        """获取视频信息 - 快速版本"""
        try:
            import websocket
            
            # 获取 WebSocket URL
            resp = requests.get(f'{self.base_url}/json', timeout=5)
            if resp.status_code != 200:
                return None
            
            all_tabs = resp.json()
            ws_url = None
            for tab in all_tabs:
                if tab.get('id') == tab_id:
                    ws_url = tab.get('webSocketDebuggerUrl', '')
                    break
            
            if not ws_url:
                return None
            
            ws = websocket.create_connection(ws_url, timeout=10)
            ws.settimeout(10)
            
            # 启用 Runtime 域
            ws.send(json.dumps({'id': 1, 'method': 'Runtime.enable'}))
            
            # 等待初始化
            time.sleep(0.5)
            
            # 使用递归 JS 检测所有 iframe 中的视频
            js_code = '''
            (function() {
                function findVideosInDoc(doc, context) {
                    var videos = doc.querySelectorAll('video');
                    if (videos.length > 0) {
                        var video = videos[0];
                        return {
                            found: true,
                            duration: video.duration || 0,
                            currentTime: video.currentTime || 0,
                            paused: video.paused,
                            src: (video.src || '').substring(0, 100),
                            id: video.id || '',
                            className: video.className || '',
                            context: context
                        };
                    }
                    return null;
                }
                
                function searchIframes(doc, prefix) {
                    var iframes = doc.querySelectorAll('iframe');
                    for (var i = 0; i < iframes.length; i++) {
                        try {
                            var iframeDoc = iframes[i].contentDocument || iframes[i].contentWindow.document;
                            var result = findVideosInDoc(iframeDoc, prefix + 'iframe-' + i);
                            if (result) return result;
                            
                            // 递归搜索嵌套 iframe
                            var nested = searchIframes(iframeDoc, prefix + 'iframe-' + i + '-');
                            if (nested) return nested;
                        } catch(e) {}
                    }
                    return null;
                }
                
                // 先搜索主文档
                var result = findVideosInDoc(document, 'main');
                if (result) return result;
                
                // 搜索 iframe
                result = searchIframes(document, '');
                if (result) return result;
                
                return {
                    found: false,
                    videoCount: document.querySelectorAll('video').length,
                    iframeCount: document.querySelectorAll('iframe').length
                };
            })();
            '''
            
            # 在主 context 执行 JS
            eval_cmd = {
                'id': 2,
                'method': 'Runtime.evaluate',
                'params': {
                    'expression': js_code,
                    'returnByValue': True
                }
            }
            
            ws.send(json.dumps(eval_cmd))
            
            # 等待响应
            start_time = time.time()
            while time.time() - start_time < 3:
                try:
                    msg = ws.recv()
                    data = json.loads(msg)
                    if data.get('id') == 2:
                        ws.close()
                        result = data.get('result', {}).get('result', {}).get('value')
                        if result and result.get('found'):
                            # 保存 context_id 为 null（主 context）
                            result['context_id'] = None
                            result['context_origin'] = 'main'
                            print(f'找到视频 (context: {result.get("context", "main")})')
                        return result
                except:
                    break
            
            ws.close()
            return None
            
        except Exception as e:
            print(f'获取视频信息失败：{e}')
            import traceback
            traceback.print_exc()
            return None
    
    def get_audio_info(self, tab_id):
        """获取音频信息"""
        try:
            import websocket
            
            # 获取 WebSocket URL
            resp = requests.get(f'{self.base_url}/json', timeout=5)
            if resp.status_code != 200:
                return None
            
            all_tabs = resp.json()
            ws_url = None
            for tab in all_tabs:
                if tab.get('id') == tab_id:
                    ws_url = tab.get('webSocketDebuggerUrl', '')
                    break
            
            if not ws_url:
                return None
            
            ws = websocket.create_connection(ws_url, timeout=10)
            ws.settimeout(10)
            ws.send(json.dumps({'id': 1, 'method': 'Runtime.enable'}))
            time.sleep(0.1)  # 减少等待时间
            
            js_code = '''
            (function() {
                var audios = document.querySelectorAll('audio');
                if (audios.length > 0) {
                    var audio = audios[0];
                    return {
                        found: true,
                        duration: audio.duration || 0,
                        currentTime: audio.currentTime || 0,
                        paused: audio.paused
                    };
                }
                return null;
            })();
            '''
            
            eval_cmd = {
                'id': 2,
                'method': 'Runtime.evaluate',
                'params': {
                    'expression': js_code,
                    'returnByValue': True
                }
            }
            
            ws.send(json.dumps(eval_cmd))
            
            start_time = time.time()
            while time.time() - start_time < 3:
                try:
                    msg = ws.recv()
                    data = json.loads(msg)
                    if data.get('id') == 2:
                        ws.close()
                        return data.get('result', {}).get('result', {}).get('value')
                except:
                    break
            
            ws.close()
            return None
            
        except Exception as e:
            return None
    
    def get_ppt_info(self, tab_id):
        """获取 PPT 信息 - 只检测当前页，不检测总页数"""
        try:
            import websocket
            
            resp = requests.get(f'{self.base_url}/json', timeout=5)
            if resp.status_code != 200:
                return None
            
            all_tabs = resp.json()
            ws_url = None
            for tab in all_tabs:
                if tab.get('id') == tab_id:
                    ws_url = tab.get('webSocketDebuggerUrl', '')
                    break
            
            if not ws_url:
                return None
            
            ws = websocket.create_connection(ws_url, timeout=10)
            ws.settimeout(10)
            ws.send(json.dumps({'id': 1, 'method': 'Runtime.enable'}))
            time.sleep(0.1)  # 减少等待时间
            
            js_code = '''
            (function() {
                // 尝试从文本获取当前页码
                var pageText = document.body.innerText;
                var pageMatch = pageText.match(/第\\s*(\\d+)\\s*页/);
                var currentPage = 0;
                
                if (pageMatch) {
                    currentPage = parseInt(pageMatch[1]);
                }
                
                // 尝试从元素获取当前页
                if (currentPage === 0) {
                    var pptElements = document.querySelectorAll('.ppt-item, .slide-item, .page-item, [class*="ppt"], [class*="slide"], [class*="page"]');
                    for (var i = 0; i < pptElements.length; i++) {
                        if (pptElements[i].style.display !== 'none' && pptElements[i].offsetParent !== null) {
                            currentPage = i + 1;
                            break;
                        }
                    }
                }
                
                // 只返回当前页，不返回总页数（因为检测不准）
                if (currentPage > 0) {
                    return {
                        found: true,
                        current: currentPage
                    };
                }
                return null;
            })();
            '''
            
            eval_cmd = {
                'id': 2,
                'method': 'Runtime.evaluate',
                'params': {
                    'expression': js_code,
                    'returnByValue': True
                }
            }
            
            ws.send(json.dumps(eval_cmd))
            
            start_time = time.time()
            while time.time() - start_time < 3:
                try:
                    msg = ws.recv()
                    data = json.loads(msg)
                    if data.get('id') == 2:
                        ws.close()
                        return data.get('result', {}).get('result', {}).get('value')
                except:
                    break
            
            ws.close()
            return None
            
        except Exception as e:
            return None
    
    def jump_audio_to_end(self, tab_id):
        """跳转音频到末尾 - 终极版本：锁定 currentTime"""
        try:
            import websocket
            
            resp = requests.get(f'{self.base_url}/json', timeout=5)
            if resp.status_code != 200:
                return None
            
            all_tabs = resp.json()
            ws_url = None
            for tab in all_tabs:
                if tab.get('id') == tab_id:
                    ws_url = tab.get('webSocketDebuggerUrl', '')
                    break
            
            if not ws_url:
                return None
            
            ws = websocket.create_connection(ws_url, timeout=10)
            ws.settimeout(10)
            ws.send(json.dumps({'id': 1, 'method': 'Runtime.enable'}))
            time.sleep(0.5)
            
            # 使用温和方法：直接设置 currentTime，不触发额外事件
            js_code = '''
            (function() {
                var audios = document.querySelectorAll('audio');
                
                for (var i = 0; i < audios.length; i++) {
                    var audio = audios[i];
                    if (audio && audio.duration > 0) {
                        // 先播放
                        audio.play().catch(function(e){});
                        
                        // 直接设置到末尾
                        var targetTime = audio.duration;
                        audio.currentTime = targetTime;
                        
                        // 保存原始的 currentTime descriptor
                        var originalDescriptor = Object.getOwnPropertyDescriptor(Audio.prototype, 'currentTime');
                        
                        // 重写 currentTime 的 setter，防止网页修改
                        Object.defineProperty(audio, 'currentTime', {
                            get: function() {
                                return targetTime;
                            },
                            set: function(value) {
                                // 只允许设置接近目标值的值
                                if (Math.abs(value - targetTime) > 0.1) {
                                    if (originalDescriptor && originalDescriptor.set) {
                                        originalDescriptor.set.call(audio, targetTime);
                                    }
                                } else {
                                    if (originalDescriptor && originalDescriptor.set) {
                                        originalDescriptor.set.call(audio, value);
                                    }
                                }
                            },
                            configurable: true
                        });
                        
                        // 10 秒后恢复
                        setTimeout(function() {
                            if (originalDescriptor) {
                                Object.defineProperty(audio, 'currentTime', originalDescriptor);
                            }
                        }, 10000);
                        
                        return {
                            found: true,
                            jumped: true,
                            duration: audio.duration,
                            currentTime: audio.currentTime
                        };
                    }
                }
                return { found: false, jumped: false };
            })();
            '''
            
            eval_cmd = {
                'id': 200,
                'method': 'Runtime.evaluate',
                'params': {
                    'expression': js_code,
                    'returnByValue': True
                }
            }
            
            ws.send(json.dumps(eval_cmd))
            
            # 等待响应
            start_time = time.time()
            while time.time() - start_time < 5:
                try:
                    msg = ws.recv()
                    data = json.loads(msg)
                    if data.get('id') == 200:
                        ws.close()
                        result = data.get('result', {}).get('result', {}).get('value')
                        if result and result.get('jumped'):
                            print(f'音频已跳转到末尾：{result["currentTime"]:.2f}/{result["duration"]:.2f} 秒')
                            # 额外等待 0.5 秒，确保网页正确更新进度显示
                            time.sleep(0.5)
                        return result
                except:
                    time.sleep(0.1)
            
            ws.close()
            return {'found': False, 'jumped': False}
            
        except Exception as e:
            print(f'跳转失败：{e}')
            return None
    
    def traverse_ppt(self, tab_id):
        """遍历 PPT 每一页 - 智能检测最后一页"""
        try:
            import websocket
            
            resp = requests.get(f'{self.base_url}/json', timeout=5)
            if resp.status_code != 200:
                return None
            
            all_tabs = resp.json()
            ws_url = None
            for tab in all_tabs:
                if tab.get('id') == tab_id:
                    ws_url = tab.get('webSocketDebuggerUrl', '')
                    break
            
            if not ws_url:
                return None
            
            ws = websocket.create_connection(ws_url, timeout=10)
            ws.settimeout(10)
            ws.send(json.dumps({'id': 1, 'method': 'Runtime.enable'}))
            time.sleep(0.5)
            
            print('开始遍历 PPT，检测页码...')
            
            # 先检测当前页码和总页数
            js_code = '''
            (function() {
                // 查找页码显示，例如 "3 / 4"
                var pageText = document.body.innerText;
                var pageMatch = pageText.match(/(\\d+)\\s*\\/\\s*(\\d+)/);
                
                if (pageMatch) {
                    return {
                        current: parseInt(pageMatch[1]),
                        total: parseInt(pageMatch[2]),
                        found: true
                    };
                }
                
                // 尝试从元素查找
                var pageDivs = document.querySelectorAll('.page, [class*="page"]');
                for (var i = 0; i < pageDivs.length; i++) {
                    var text = pageDivs[i].innerText;
                    var match = text.match(/(\\d+)\\s*\\/\\s*(\\d+)/);
                    if (match) {
                        return {
                            current: parseInt(match[1]),
                            total: parseInt(match[2]),
                            found: true
                        };
                    }
                }
                
                return { found: false };
            })();
            '''
            
            eval_cmd = {
                'id': 300,
                'method': 'Runtime.evaluate',
                'params': {
                    'expression': js_code,
                    'returnByValue': True
                }
            }
            
            ws.send(json.dumps(eval_cmd))
            
            start_time = time.time()
            total_pages = 0
            current_page = 0
            while time.time() - start_time < 1:  # 减少等待时间到 1 秒
                try:
                    msg = ws.recv()
                    data = json.loads(msg)
                    if data.get('id') == 300:
                        result = data.get('result', {}).get('result', {}).get('value')
                        if result and result.get('found'):
                            total_pages = result.get('total', 0)
                            current_page = result.get('current', 1)
                            print(f'检测到 PPT 共 {total_pages} 页，当前第 {current_page} 页')
                        break
                except:
                    break
            
            # 计算需要点击的次数
            pages_to_click = total_pages - current_page
            print(f'需要浏览 {pages_to_click} 页')
            
            # 循环点击到最后一页
            clicked_pages = 0
            consecutive_failures = 0
            max_failures = 3
            
            while clicked_pages < pages_to_click and consecutive_failures < max_failures:
                # 精确匹配下一页按钮
                js_code = '''
                (function() {
                    // 优先查找包含"下一页"文本的按钮
                    var buttons = document.querySelectorAll('button');
                    for (var i = 0; i < buttons.length; i++) {
                        if (buttons[i].innerText.includes('下一页') || buttons[i].textContent.includes('下一页')) {
                            // 检查按钮是否可点击
                            if (!buttons[i].disabled && buttons[i].offsetParent !== null) {
                                buttons[i].click();
                                return { success: true, method: 'button' };
                            }
                        }
                    }
                    
                    // 尝试查找 el-button--mini 类的按钮
                    var miniButtons = document.querySelectorAll('.el-button--mini');
                    for (var i = 0; i < miniButtons.length; i++) {
                        if (miniButtons[i].innerText.includes('下一页') || miniButtons[i].textContent.includes('下一页')) {
                            if (!miniButtons[i].disabled && miniButtons[i].offsetParent !== null) {
                                miniButtons[i].click();
                                return { success: true, method: 'mini' };
                            }
                        }
                    }
                    
                    // 尝试查找 data-v- 开头的按钮
                    var dataButtons = document.querySelectorAll('[data-v-]');
                    for (var i = 0; i < dataButtons.length; i++) {
                        if (dataButtons[i].tagName === 'BUTTON' && (dataButtons[i].innerText.includes('下一页') || dataButtons[i].textContent.includes('下一页'))) {
                            if (!dataButtons[i].disabled && dataButtons[i].offsetParent !== null) {
                                dataButtons[i].click();
                                return { success: true, method: 'data-v' };
                            }
                        }
                    }
                    
                    return { success: false, method: 'none' };
                })();
                '''
                
                eval_cmd = {
                    'id': 400 + clicked_pages + 1,
                    'method': 'Runtime.evaluate',
                    'params': {
                        'expression': js_code,
                        'returnByValue': True
                    }
                }
                
                ws.send(json.dumps(eval_cmd))
                
                start_time = time.time()
                success = False
                while time.time() - start_time < 0.5:  # 减少等待时间到 0.5 秒
                    try:
                        msg = ws.recv()
                        data = json.loads(msg)
                        if data.get('id') == 400 + clicked_pages + 1:
                            result = data.get('result', {}).get('result', {}).get('value')
                            if result:
                                success = result.get('success', False)
                            break
                    except:
                        break
                
                if success:
                    # 点击成功后，检测当前页码
                    clicked_pages += 1
                    expected_page = current_page + clicked_pages
                    
                    # 检测当前页码
                    check_js = '''
                    (function() {
                        var pageText = document.body.innerText;
                        var pageMatch = pageText.match(/(\\d+)\\s*\\/\\s*(\\d+)/);
                        
                        if (pageMatch) {
                            return {
                                current: parseInt(pageMatch[1]),
                                total: parseInt(pageMatch[2])
                            };
                        }
                        
                        var pageDivs = document.querySelectorAll('.page, [class*="page"]');
                        for (var i = 0; i < pageDivs.length; i++) {
                            var text = pageDivs[i].innerText;
                            var match = text.match(/(\\d+)\\s*\\/\\s*(\\d+)/);
                            if (match) {
                                return {
                                    current: parseInt(match[1]),
                                    total: parseInt(match[2])
                                };
                            }
                        }
                        
                        return { current: 0, total: 0 };
                    })();
                    '''
                    
                    check_cmd = {
                        'id': 500 + clicked_pages,
                        'method': 'Runtime.evaluate',
                        'params': {
                            'expression': check_js,
                            'returnByValue': True
                        }
                    }
                    
                    ws.send(json.dumps(check_cmd))
                    
                    start_time = time.time()
                    while time.time() - start_time < 0.3:  # 减少等待时间到 0.3 秒
                        try:
                            msg = ws.recv()
                            data = json.loads(msg)
                            if data.get('id') == 500 + clicked_pages:
                                result = data.get('result', {}).get('result', {}).get('value')
                                if result and result.get('current') > 0:
                                    detected_page = result.get('current')
                                    is_last = detected_page >= result.get('total', 0)
                                    if is_last:
                                        print(f'  第 {detected_page} 页 (最后一页)')
                                    else:
                                        print(f'  第 {detected_page} 页')
                                    
                                    # 如果是最后一页，停止
                                    if is_last:
                                        print('已到达最后一页')
                                        ws.close()
                                        if clicked_pages > 0:
                                            print(f'PPT 遍历完成，共浏览 {clicked_pages} 页')
                                        return
                                break
                        except:
                            break
                    
                    consecutive_failures = 0
                    
                    # 10ms 延迟，更快
                    time.sleep(0.01)
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= max_failures:
                        print(f'  无法继续翻页，当前在第 {current_page + clicked_pages} 页')
                    else:
                        print(f'  第 {current_page + clicked_pages + 1} 页点击失败，重试中...')
                        time.sleep(0.1)
            
            ws.close()
            if clicked_pages > 0:
                print(f'PPT 遍历完成，共浏览 {clicked_pages} 页')
            
        except Exception as e:
            print(f'遍历失败：{e}')
            import traceback
            traceback.print_exc()
    
    def click_next(self, tab_id):
        """点击下一个课件"""
        try:
            import websocket
            
            resp = requests.get(f'{self.base_url}/json', timeout=5)
            if resp.status_code != 200:
                return None
            
            all_tabs = resp.json()
            ws_url = None
            for tab in all_tabs:
                if tab.get('id') == tab_id:
                    ws_url = tab.get('webSocketDebuggerUrl', '')
                    break
            
            if not ws_url:
                return None
            
            ws = websocket.create_connection(ws_url, timeout=10)
            ws.settimeout(10)
            ws.send(json.dumps({'id': 1, 'method': 'Runtime.enable'}))
            time.sleep(0.5)
            
            # 先检查是否是"暂无"课件
            check_js = '''
            (function() {
                var nextDivs = document.querySelectorAll('.next, [class*="next"]');
                for (var i = 0; i < nextDivs.length; i++) {
                    var text = nextDivs[i].innerText || nextDivs[i].textContent;
                    if (text.includes('暂无')) {
                        return { isNone: true };
                    }
                }
                return { isNone: false };
            })();
            '''
            
            check_cmd = {
                'id': 599,
                'method': 'Runtime.evaluate',
                'params': {
                    'expression': check_js,
                    'returnByValue': True
                }
            }
            
            ws.send(json.dumps(check_cmd))
            
            start_time = time.time()
            is_none = False
            while time.time() - start_time < 2:
                try:
                    msg = ws.recv()
                    data = json.loads(msg)
                    if data.get('id') == 599:
                        result = data.get('result', {}).get('result', {}).get('value')
                        if result and result.get('isNone'):
                            is_none = True
                        break
                except:
                    break
            
            if is_none:
                ws.close()
                print('跳转失败：暂无课件')
                return {'success': False, 'reason': 'none'}
            
            # 查找并点击下一个课件的链接
            js_code = '''
            (function() {
                // 查找 class 包含 "next" 的元素
                var nextDivs = document.querySelectorAll('.next, [class*="next"]');
                
                for (var i = 0; i < nextDivs.length; i++) {
                    // 查找其中的链接
                    var links = nextDivs[i].querySelectorAll('a, .el-link');
                    if (links.length > 0) {
                        // 点击第一个链接
                        links[0].click();
                        return { success: true, method: 'next-div' };
                    }
                }
                
                // 尝试查找包含"下一个"文本的链接
                var allLinks = document.querySelectorAll('a, .el-link');
                for (var i = 0; i < allLinks.length; i++) {
                    var text = allLinks[i].innerText || allLinks[i].textContent;
                    if (text.includes('下一个') || text.includes('下一课')) {
                        allLinks[i].click();
                        return { success: true, method: 'text-match' };
                    }
                }
                
                return { success: false, method: 'none' };
            })();
            '''
            
            eval_cmd = {
                'id': 600,
                'method': 'Runtime.evaluate',
                'params': {
                    'expression': js_code,
                    'returnByValue': True
                }
            }
            
            ws.send(json.dumps(eval_cmd))
            
            start_time = time.time()
            while time.time() - start_time < 3:
                try:
                    msg = ws.recv()
                    data = json.loads(msg)
                    if data.get('id') == 600:
                        ws.close()
                        result = data.get('result', {}).get('result', {}).get('value')
                        if result and result.get('success'):
                            print(f'成功点击下一个课件 (方法：{result.get("method", "unknown")})')
                        else:
                            print('未找到下一个课件的链接')
                        return result
                except:
                    break
            
            ws.close()
            return {'success': False}
            
        except Exception as e:
            print(f'点击失败：{e}')
            import traceback
            traceback.print_exc()
            return None
    
    def jump_to_end(self, tab_id, context_id=None):
        """跳转视频到末尾 - 强制版本"""
        try:
            import websocket
            
            # 获取 WebSocket URL
            resp = requests.get(f'{self.base_url}/json', timeout=5)
            if resp.status_code != 200:
                return None
            
            all_tabs = resp.json()
            ws_url = None
            for tab in all_tabs:
                if tab.get('id') == tab_id:
                    ws_url = tab.get('webSocketDebuggerUrl', '')
                    break
            
            if not ws_url:
                return None
            
            ws = websocket.create_connection(ws_url, timeout=10)
            ws.settimeout(10)
            
            # 启用 Runtime 域
            ws.send(json.dumps({'id': 1, 'method': 'Runtime.enable'}))
            time.sleep(0.5)
            
            # 强制跳转 JS 代码
            js_code = '''
            (function() {
                function forceJumpVideo(doc) {
                    var videos = doc.querySelectorAll('video');
                    for (var i = 0; i < videos.length; i++) {
                        var video = videos[i];
                        if (video && video.duration > 0) {
                            // 方法 1: 先播放视频
                            video.play();
                            
                            // 方法 2: 添加 timeupdate 拦截器，防止被恢复
                            var timeupdateHandler = function(e) {
                                if (Math.abs(video.currentTime - video.duration) > 0.5) {
                                    video.currentTime = video.duration;
                                }
                            };
                            video.addEventListener('timeupdate', timeupdateHandler, true);
                            
                            // 方法 3: 直接设置
                            video.currentTime = video.duration;
                            
                            // 方法 4: 短暂延迟后再次确认
                            setTimeout(function() {
                                video.currentTime = video.duration;
                            }, 50);
                            
                            // 方法 5: 1 秒后移除拦截器
                            setTimeout(function() {
                                video.removeEventListener('timeupdate', timeupdateHandler, true);
                            }, 1000);
                            
                            return {
                                found: true,
                                jumped: true,
                                duration: video.duration,
                                currentTime: video.currentTime
                            };
                        }
                    }
                    return { found: false, jumped: false };
                }
                
                function searchIframes(doc) {
                    var iframes = doc.querySelectorAll('iframe');
                    for (var i = 0; i < iframes.length; i++) {
                        try {
                            var iframeDoc = iframes[i].contentDocument || iframes[i].contentWindow.document;
                            var result = forceJumpVideo(iframeDoc);
                            if (result.found) return result;
                            
                            var nested = searchIframes(iframeDoc);
                            if (nested.found) return nested;
                        } catch(e) {}
                    }
                    return { found: false, jumped: false };
                }
                
                var result = forceJumpVideo(document);
                if (result.found) return result;
                
                return searchIframes(document);
            })();
            '''
            
            eval_cmd = {
                'id': 200,
                'method': 'Runtime.evaluate',
                'params': {
                    'expression': js_code,
                    'returnByValue': True
                }
            }
            
            ws.send(json.dumps(eval_cmd))
            
            start_time = time.time()
            while time.time() - start_time < 3:
                try:
                    msg = ws.recv()
                    data = json.loads(msg)
                    if data.get('id') == 200:
                        ws.close()
                        result = data.get('result', {}).get('result', {}).get('value')
                        if result and result.get('jumped'):
                            print(f'视频已跳转到末尾：{result["currentTime"]:.2f}/{result["duration"]:.2f} 秒')
                        return result
                except:
                    break
            
            ws.close()
            return {'found': False, 'jumped': False}
            
        except Exception as e:
            print(f'跳转失败：{e}')
            return None
        
        if result and result.get('jumped'):
            print(f'视频已跳转到末尾：{result["currentTime"]:.2f}/{result["duration"]:.2f} 秒 (位置：{result.get("context", "unknown")})')
            return True
        return False
    
    def cleanup(self):
        """清理资源"""
        pass


def main():
    print('使用说明：')
    print('1. 在启动的浏览器中登录智慧职教并打开课程')
    print('2. 选择对应的标签页编号，可以输入 -r 刷新标签页列表')
    print('\nTips:')
    print('适配大部分网站，也包括Bilibili哦')
    print('极其不推荐将该程序用于超星学习通\n')
    
    player = ChaoxingAutoPlayer()
    
    print('按回车键启动或连接到 Edge 浏览器...')
    input()
    
    print('正在启动 Edge 浏览器...')
    if not player.start_edge():
        print('启动 Edge 失败')
        input('按回车键退出...')
        return
    
    if not player.check_browser():
        print('无法连接到 Edge')
        input('按回车键退出...')
        return
    
    while True:
        print('已连接到 Edge 浏览器')
        print('')
        
        # 模式选择
        print('请选择模式：')
        print('  1. 自动选择模式（自动查找智慧职教标签页）')
        print('  2. 手动选择模式（手动选择标签页）')
        
        while True:
            mode_choice = input('请输入模式编号 (1/2): ').strip()
            if mode_choice in ['1', '2']:
                break
            print('请输入 1 或 2')
        
        auto_mode = (mode_choice == '1')
        auto_selected = False
        tabs = []
        
        if auto_mode:
            print('\n=== 自动选择模式 ===')
            target_url = 'https://zjy2.icve.com.cn/study/coursePreview/spoccourseIndex/courseware?id='
            
            while True:
                tabs = player.get_tabs()
                if not tabs:
                    print('未找到任何标签页，等待 2 秒后重试...')
                    time.sleep(2)
                    continue
                
                # 尝试自动选择
                auto_selected = False
                for i, tab in enumerate(tabs):
                    url = tab.get('url', '')
                    if target_url in url:
                        tab_index = i
                        auto_selected = True
                        print(f'\n找到智慧职教标签页！')
                        print(f'自动选择：{tab.get("title", "")[:50]}')
                        break
                
                if auto_selected:
                    break
                
                print('未找到智慧职教标签页，等待 2 秒后重试... (按 Ctrl+C 退出)')
                time.sleep(2)
        else:
            print('\n=== 手动选择模式 ===')
            
            while True:
                tabs = player.get_tabs()
                if not tabs:
                    print('未找到任何标签页')
                    print('输入 -r 刷新，输入 0 退出')
                    choice = input('请选择：').strip()
                    if choice == '0':
                        return
                    elif choice == '-r':
                        continue
                    else:
                        continue
                
                print(f'找到 {len(tabs)} 个标签页:')
                for i, tab in enumerate(tabs):
                    title = tab.get('title', '无标题')[:50]
                    url = tab.get('url', '')[:50]
                    print(f'  {i+1}. [{url}] {title}')
                
                choice = input('\n请选择要操作的标签页编号 (输入 0 新建标签页，-r 刷新): ').strip()
                
                if choice == '-r':
                    continue
                
                if choice == '0':
                    print('请在新建的标签页中登录超星并打开视频')
                    print('然后重新运行脚本，选择该标签页')
                    input('按回车键退出...')
                    return
                
                try:
                    tab_index = int(choice) - 1
                except:
                    print('输入无效，请输入数字编号')
                    continue
                
                if tab_index < 0 or tab_index >= len(tabs):
                    print('选择无效')
                    continue
                
                break
        
        tab = tabs[tab_index]
        tab_id = tab.get('id')
        url = tab.get('url', '')
        print(f'已选择标签页：{tab.get("title", "无标题")}')
        print(f'URL: {url}')
        print(f'tab_id: {tab_id}')
        if auto_selected:
            print(f'自动选择，索引：{tab_index}')
        
        print('')
        print('正在检测媒体资源...')
        
        # 检测视频
        video_info = player.get_video_info(tab_id)
        
        if video_info and video_info.get('found'):
            print(f'视频：{video_info.get("currentTime", 0):.2f}/{video_info.get("duration", 0):.2f} 秒')
        else:
            print('未检测到视频')
        
        # 检测音频
        audio_info = player.get_audio_info(tab_id)
        if audio_info and audio_info.get('found'):
            print(f'音频：{audio_info.get("currentTime", 0):.2f}/{audio_info.get("duration", 0):.2f} 秒')
        else:
            print('未检测到音频')
        
        # 检测 PPT
        ppt_info = player.get_ppt_info(tab_id)
        if ppt_info and ppt_info.get('found'):
            print(f'PPT: 第 {ppt_info.get("current", 0)} 页')
        else:
            print('未检测到 PPT')
        
        print('')
        print('操作完成！浏览器会保持打开状态')
        print('输入 quit 退出，-r 重新选择模式')
        print('命令：-skip (智能跳过), video -skip (跳过视频), audio -skip (跳过音频), ppt -skip (遍历 PPT), next (下一个课件), autorun (自动运行)')
        
        should_restart = False
        while not should_restart:
            cmd = input('<控制台>:').strip().lower()
            if cmd == 'quit':
                print('退出程序...')
                return
            elif cmd == '-r':
                # 跳回到模式选择
                print('\n' + '='*50)
                print('重新选择模式...')
                print('='*50 + '\n')
                should_restart = True
            
            elif cmd == 'video -skip':
                print('跳过视频...')
                player.jump_to_end(tab_id)
            
            elif cmd == 'audio -skip':
                print('跳过音频...')
                player.jump_audio_to_end(tab_id)
            
            elif cmd == 'ppt -skip':
                print('遍历 PPT...')
                player.traverse_ppt(tab_id)
            
            elif cmd == 'next':
                print('跳转到下一个课件...')
                player.click_next(tab_id)
            
            elif cmd == '-skip':
                print('智能跳过（优先视频 > 音频 > PPT）...')
                
                # 优先检测视频
                video_info = player.get_video_info(tab_id)
                if video_info and video_info.get('found'):
                    print(f'检测到视频：{video_info.get("currentTime", 0):.2f}/{video_info.get("duration", 0):.2f} 秒')
                    player.jump_to_end(tab_id)
                    print('已跳过视频')
                else:
                    # 其次检测音频
                    audio_info = player.get_audio_info(tab_id)
                    if audio_info and audio_info.get('found'):
                        print(f'检测到音频：{audio_info.get("currentTime", 0):.2f}/{audio_info.get("duration", 0):.2f} 秒')
                        player.jump_audio_to_end(tab_id)
                        print('已跳过音频')
                    else:
                        # 最后检测 PPT
                        ppt_info = player.get_ppt_info(tab_id)
                        if ppt_info and ppt_info.get('found'):
                            print(f'检测到 PPT: 第 {ppt_info.get("current", 0)} 页')
                            player.traverse_ppt(tab_id)
                        else:
                            print('未检测到任何媒体资源（视频、音频、PPT）')
            
            elif cmd == 'autorun':
                print('开始自动运行...')
                print('循环执行：-skip -> next')
                print('')
                
                run_count = 0
                while True:
                    run_count += 1
                    print(f'=== 第 {run_count} 个课件 ===')
                    
                    # 执行 -skip
                    is_audio = False
                    
                    # 检测视频
                    video_info = player.get_video_info(tab_id)
                    if video_info and video_info.get('found'):
                        print(f'检测到视频：{video_info.get("currentTime", 0):.2f}/{video_info.get("duration", 0):.2f} 秒')
                        player.jump_to_end(tab_id)
                        print('已跳过视频')
                    else:
                        # 检测音频
                        audio_info = player.get_audio_info(tab_id)
                        if audio_info and audio_info.get('found'):
                            print(f'检测到音频：{audio_info.get("currentTime", 0):.2f}/{audio_info.get("duration", 0):.2f} 秒')
                            player.jump_audio_to_end(tab_id)
                            print('已跳过音频')
                            is_audio = True
                        else:
                            # 检测 PPT
                            ppt_info = player.get_ppt_info(tab_id)
                            if ppt_info and ppt_info.get('found'):
                                print(f'检测到 PPT: 第 {ppt_info.get("current", 0)} 页')
                                player.traverse_ppt(tab_id)
                            else:
                                print('未检测到任何媒体资源（视频、音频、PPT）')
                    
                    # 音频跳过后额外等待 0.5 秒
                    if is_audio:
                        time.sleep(0.5)
                    
                    print('')
                    
                    # 执行 next
                    result = player.click_next(tab_id)
                    
                    # 检查是否是"暂无"课件
                    if result and result.get('reason') == 'none':
                        print('')
                        print('自动运行结束')
                        break
                    
                    print('')
                    time.sleep(0.3)  # 等待页面加载
            
            else:
                print('无效命令，输入 quit 退出，-r 重新选择模式')
                print('可用命令：-skip (智能跳过), video -skip, audio -skip, ppt -skip, next, autorun')


if __name__ == '__main__':
    main()
