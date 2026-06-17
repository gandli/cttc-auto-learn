"""进程管理 - 清理多余的 Playwright Chrome 进程

确保单实例运行，防止网站检测多开。
"""
import subprocess
import os
import sys
import tempfile
from pathlib import Path

# 单实例锁文件
LOCK_FILE = Path(tempfile.gettempdir()) / "cttc-auto.lock"


def check_single_instance(log) -> bool:
    """检查是否已有实例在运行，如果是则退出"""
    if LOCK_FILE.exists():
        try:
            old_pid = int(LOCK_FILE.read_text().strip())
            # 检查进程是否还在
            result = subprocess.run(
                ['tasklist', '/FI', f'PID eq {old_pid}', '/FO', 'CSV', '/NH'],
                capture_output=True, text=True
            )
            if 'python' in (result.stdout or '').lower():
                log.error(f"❌ 已有实例在运行 (PID {old_pid})，请先关闭后再启动")
                return False
        except (ValueError, FileNotFoundError):
            pass
    # 写入当前 PID
    LOCK_FILE.write_text(str(os.getpid()))
    return True


def release_lock():
    """释放单实例锁"""
    try:
        LOCK_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def kill_other_chrome_processes(log) -> int:
    """杀掉所有由 Playwright 启动的 Chrome 进程（排除当前进程树）"""
    killed = 0
    
    try:
        result = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq chrome.exe', '/FO', 'CSV', '/NH'],
            capture_output=True, text=True, encoding='utf-8'
        )
        
        if result.returncode != 0:
            return 0
        
        chrome_pids = []
        for line in (result.stdout or "").strip().split('\n'):
            if not line.strip():
                continue
            parts = line.split('"')
            if len(parts) >= 4:
                try:
                    chrome_pids.append(int(parts[3]))
                except ValueError:
                    continue
        
        if not chrome_pids:
            return 0
        
        log.info(f"🔍 发现 {len(chrome_pids)} 个 Chrome 进程")
        
        # 获取当前进程树的 PID
        current_pid = os.getpid()
        protected_pids = {current_pid}
        try:
            import psutil
            proc = psutil.Process(current_pid)
            for p in proc.parents():
                protected_pids.add(p.pid)
            for p in proc.children(recursive=True):
                protected_pids.add(p.pid)
        except ImportError:
            pass
        
        for pid in chrome_pids:
            if pid in protected_pids:
                continue
            try:
                cmd_result = subprocess.run(
                    ['wmic', 'process', 'where', f'ProcessId={pid}', 'get', 'CommandLine'],
                    capture_output=True, text=True, encoding='utf-8'
                )
                cmd_line = (cmd_result.stdout or "").lower()
                
                # Playwright 特征：临时目录 + 特定参数
                is_playwright = any(m in cmd_line for m in [
                    '--remote-debugging-port',
                    '--no-first-run',
                    'playwright',
                    'ms-playwright',
                ])
                # 临时目录中的 Chrome 也视为 Playwright
                if not is_playwright:
                    for tmp_kw in ['temp\\\\', 'tmp\\\\', 'temp/', 'tmp/']:
                        if tmp_kw in cmd_line:
                            is_playwright = True
                            break
                
                # 只杀掉 cttc-auto-learn 相关的进程，不杀其他 Playwright 进程（如 Hermes Agent）
                is_cttc = any(m in cmd_line for m in [
                    'cttc',
                    'mooc.ctt.cn',
                    'auto-learn',
                ])
                
                if is_playwright and is_cttc:
                    subprocess.run(['taskkill', '/F', '/PID', str(pid)], capture_output=True)
                    killed += 1
            except Exception:
                continue
        
        if killed > 0:
            log.info(f"✅ 已清理 {killed} 个多余 Chrome 进程")
    except Exception as e:
        log.warn(f"⚠️ 清理进程失败: {e}")
    
    return killed
