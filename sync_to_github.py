# -*- coding: utf-8 -*-
r"""C2 方案同步守护: 每 10 分钟导出工单并 git push 到 GitHub 公开仓库。

数据经 jsDelivr CDN 加速, 同事外网零成本查看历史工单; 标记完成等写操作由前端
直接 POST 到 cpolar 内网地址 (开机时可用), 同样零成本。

依赖: 本机 PortableGit (D:\.workbuddy\vendor\PortableGit\mingw64\bin\git.exe)。
首次部署需先跑 setup_github.py 配置 remote 与凭证 (用户名 + token)。

用法:
  常驻(默认):  pythonw sync_to_github.py
  单次推送:     python sync_to_github.py once
"""
import os
import sys
import time
import logging
import subprocess

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO_DIR = os.path.join(BASE, "cloudbase", "web_github")
GIT = r"D:\.workbuddy\vendor\PortableGit\mingw64\bin\git.exe"
LOG = os.path.join(REPO_DIR, "sync_github.log")

logging.basicConfig(filename=LOG, level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("sync_gh")

sys.path.insert(0, REPO_DIR)
import export_orders  # noqa: E402


def git(*args):
    try:
        r = subprocess.run([GIT, *args], cwd=REPO_DIR,
                           capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            out = (r.stderr or r.stdout).strip()
            # "Everything up-to-date" 不是错误, 忽略
            if "up-to-date" in out:
                return True
            log.error("git %s failed: %s", args, out)
            return False
        return True
    except Exception as e:
        log.error("git %s exception: %s", args, e)
        return False


def push_once():
    n = export_orders.export(mask=True)
    try:
        st = subprocess.run([GIT, "status", "--porcelain"], cwd=REPO_DIR,
                            capture_output=True, text=True, timeout=30)
        if not st.stdout.strip():
            log.info("no change, skip push (%d orders)", n)
            return n
    except Exception as e:
        log.warning("status check failed: %s", e)
    git("add", "-A")
    git("commit", "-m", "orders %s" % time.strftime("%Y%m%d-%H%M%S"))
    ok = git("push", "origin", "main")
    if ok:
        log.info("pushed %d orders", n)
    else:
        log.warning("push failed (maybe remote not configured? run setup_github.py)")
    return n


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "daemon"
    if mode == "once":
        push_once()
        return
    LOOP = 600  # 10 分钟一轮, 工单对实时性要求不高, 省调用量
    log.info("github sync daemon start, loop %ds", LOOP)
    while True:
        try:
            push_once()
        except Exception as e:
            log.error("push loop error: %s", e)
        time.sleep(LOOP)


if __name__ == "__main__":
    main()
