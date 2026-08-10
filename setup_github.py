# -*- coding: utf-8 -*-
"""C2 一键部署: 建 GitHub 公开仓库 + 启用 Pages + 推送前端 + 回写 config。

交互输入: GitHub 用户名、Personal Access Token(不回显)、仓库名。
完成后输出:
  - GitHub Pages 站点地址 (同事外网看板)
  - jsDelivr 数据地址 (前端读取的 orders.json)
脚本会自动用 jsDelivr 地址回写 web_github/config.js 的 DATA_URL 并重新推送。

前置: 需要一个有 repo 权限的 GitHub Personal Access Token
      (https://github.com/settings/tokens -> 勾选 repo; 若用 fine-grained 还需 Pages 写权限)
"""
import getpass
import json
import os
import sys
import time
import subprocess
import urllib.request
import urllib.parse
import urllib.error

BASE = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = BASE
GIT = r"D:\.workbuddy\vendor\PortableGit\mingw64\bin\git.exe"
CFG_JS = os.path.join(REPO_DIR, "config.js")
API = "https://api.github.com"


def git(*args, check=True):
    r = subprocess.run([GIT, *args], cwd=REPO_DIR, capture_output=True, text=True, timeout=120)
    if check and r.returncode != 0:
        print("git error:", r.stderr.strip() or r.stdout.strip())
    return r


def gh_api(method, path, token, data=None):
    url = API + path
    headers = {"Authorization": "token " + token,
               "Accept": "application/vnd.github+json", "User-Agent": "wechat-watcher"}
    req = urllib.request.Request(url, headers=headers, method=method)
    if data is not None:
        req.data = json.dumps(data).encode("utf-8")
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8"), resp.status
    except urllib.error.HTTPError as e:
        return e.read().decode("utf-8", "replace"), e.code


def main():
    print("=== C2 GitHub 一键部署 ===")
    user = input("GitHub 用户名: ").strip()
    token = getpass.getpass("GitHub Personal Access Token (输入不回显): ").strip()
    repo = input("仓库名 [elevator-orders-public]: ").strip() or "elevator-orders-public"
    if not user or not token:
        print("用户名和 token 不能为空")
        return

    # 1. 建公开仓库(已存在则忽略)
    body, st = gh_api("POST", "/user/repos", token, {
        "name": repo, "private": False,
        "description": "盛尧电梯维修工单 - 外网只读看板数据 (自动导出)",
        "auto_init": False, "has_issues": False, "has_wiki": False
    })
    if st == 201:
        print("仓库已创建: https://github.com/%s/%s" % (user, repo))
    elif st in (422, 409):
        print("仓库已存在, 继续...")
    else:
        print("建仓库返回 (%d): %s" % (st, body[:300]))
        print("仍尝试继续推送(若仓库已存在)...")

    # 2. git init + remote
    if not os.path.exists(os.path.join(REPO_DIR, ".git")):
        git("init")
        git("config", "user.email", "wb@local")
        git("config", "user.name", "wechat-watcher")
    auth_user = urllib.parse.quote(user, safe="")
    remote_url = "https://%s@github.com/%s/%s.git" % (urllib.parse.quote(token, safe=""), auth_user, repo)
    git("remote", "remove", "origin", check=False)
    git("remote", "add", "origin", remote_url)
    git("branch", "-M", "main", check=False)

    # 3. 回写 config.js 的 DATA_URL (REPLACE_OWNER / REPLACE_REPO 占位符)
    jsdelivr = "https://cdn.jsdelivr.net/gh/%s/%s@main/orders.json" % (user, repo)
    try:
        with open(CFG_JS, "r", encoding="utf-8") as f:
            txt = f.read()
        if "REPLACE_OWNER" in txt or "REPLACE_REPO" in txt:
            txt2 = txt.replace("REPLACE_OWNER", user).replace("REPLACE_REPO", repo)
            with open(CFG_JS, "w", encoding="utf-8") as f:
                f.write(txt2)
            print("已回写 config.js DATA_URL:", jsdelivr)
        else:
            print("config.js 已是最终地址, 跳过回写")
    except Exception as e:
        print("回写 config.js 失败:", e)

    # 4. 首次 commit + push
    git("add", "-A")
    git("commit", "-m", "init C2 dashboard %s" % time.strftime("%Y%m%d-%H%M%S"), check=False)
    pr = git("push", "-u", "origin", "main")
    if pr.returncode != 0:
        print("首次 push 失败, 请检查 token 权限 / 仓库名 / 网络")
        return
    print("已推送到 GitHub")

    # 5. 启用 Pages (站点 https://<user>.github.io/<repo>/)
    _, st2 = gh_api("POST", "/repos/%s/%s/pages" % (user, repo), token,
                   {"source": {"branch": "main", "path": "/"}})
    pages_url = "https://%s.github.io/%s/" % (user, repo)
    if st2 in (201, 409):
        print("GitHub Pages 已启用:", pages_url)
    else:
        print("Pages 可能需手动启用: 仓库 Settings -> Pages -> Source 选 main 分支 / 根目录")

    print("\n=== 部署完成 ===")
    print("外网看板地址:", pages_url)
    print("数据地址(jsDelivr):", jsdelivr)
    print("后续: 运行 sync_to_github.py 守护进程, 每10分钟自动导出并推送最新工单")


if __name__ == "__main__":
    main()
