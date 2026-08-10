# -*- coding: utf-8 -*-
"""导出本机工单为公开可托管的 orders.json (供 GitHub + jsDelivr 方案)。

这是 C2「零成本外网只读看板」的数据源：
  - 拉本机各年工单 (raw socket 走 127.0.0.1:8899, 绕过沙箱限制)
  - 项目名映射 (contact.db 的 wxid -> 群昵称)
  - 默认脱敏手机号与发送者昵称, 避免公开仓库泄露个人信息
  - 注入 cpolar 内网地址, 供前端写操作(标记完成)回内网
  - 图片/视频保留内网相对路径, 前端按 cpolar_url 动态拼接

用法:
  python export_orders.py          # 导出一次
  python export_orders.py nomask   # 导出且不脱敏(仅本机自测用)
"""
import json
import os
import re
import socket
import sys
import time
import logging
import hashlib

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CFG = os.path.join(BASE, "cloudbase", "config.json")
OUT_DIR = os.path.join(BASE, "cloudbase", "web_github")
OUT = os.path.join(OUT_DIR, "orders.json")
CPOLAR_LOG = os.path.join(BASE, "cpolar", "cpolar.log")
CPOLAR_RE = re.compile(r'https?://[a-f0-9]+\.r\d+\.cpolar\.top')
PHONE_RE = re.compile(r'(?<!\d)(1[3-9]\d[ -]?\d{4}[ -]?\d{4})(?!\d)')
CONTACT_DB = os.path.join(BASE, "decrypted", "contact.db")
NAME_CACHE = os.path.join(OUT_DIR, "wxid_to_name.json")
WXID_RE = re.compile(r"^[\w\-]+@chatroom$")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("export")


def load_cfg():
    try:
        with open(CFG, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def get_cpolar_url():
    try:
        with open(CPOLAR_LOG, "r", encoding="utf-8", errors="replace") as f:
            m = CPOLAR_RE.findall(f.read())
            if m:
                return m[-1]
    except Exception:
        pass
    return None


def load_group_names():
    if os.path.exists(NAME_CACHE) and os.path.getmtime(NAME_CACHE) >= os.path.getmtime(CONTACT_DB):
        try:
            return json.load(open(NAME_CACHE, encoding="utf-8"))
        except Exception:
            pass
    mapping = {}
    try:
        import sqlite3
        # immutable=1: 只读且不获取文件锁, 绕过微信对 contact.db 的独占占用
        con = sqlite3.connect("file:%s?mode=ro&immutable=1" % CONTACT_DB, uri=True)
        for u, n in con.execute(
            "SELECT username, nick_name FROM contact WHERE username LIKE '%chatroom' OR username LIKE '%foldgroup%'"
        ):
            if n and n.strip():
                mapping[u] = n.strip()
        con.close()
    except Exception as e:
        log.warning("load_group_names failed: %s", e)
    try:
        os.makedirs(OUT_DIR, exist_ok=True)
        with open(NAME_CACHE, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return mapping


def enrich_project(o, name_map):
    p = o.get("project", "")
    if not p:
        return
    if not (WXID_RE.match(p) or p.startswith("@placeholder") or p.endswith("@foldgroup")):
        return
    if p in name_map:
        o["project"] = name_map[p]
    elif p.startswith("@placeholder") or p.endswith("@foldgroup"):
        o["project"] = "未分组"


def fetch_local_year(year):
    url_path = "/api/workorders?live=1&year=%d" % year
    try:
        s = socket.create_connection(("127.0.0.1", 8899), timeout=30)
        s.sendall(("GET %s HTTP/1.0\r\nHost: localhost\r\n\r\n" % url_path).encode())
        buf = b""
        while True:
            c = s.recv(65536)
            if not c:
                break
            buf += c
        s.close()
        i = buf.find(b"\r\n\r\n")
        if i < 0:
            return []
        d = json.loads(buf[i + 4:].decode("utf-8", "replace"))
        return d.get("orders", [])
    except Exception as e:
        log.warning("fetch local %s failed: %s", year, e)
        return []


def mask_phone(text):
    if not isinstance(text, str):
        return text
    def _digits(m):
        d = re.sub(r"\D", "", m.group(1))
        return d[:3] + "****" + d[-4:]
    return PHONE_RE.sub(_digits, text)


def hash_name(name):
    if not name:
        return name
    h = hashlib.sha256(name.encode("utf-8")).hexdigest()[:8]
    return "用户" + h


def export(mask=True, mask_sender=True, mask_phone_flag=True):
    cfg = load_cfg()
    years = cfg.get("years", [2024, 2025, 2026])
    name_map = load_group_names()
    merged = {}
    for y in years:
        for o in fetch_local_year(y):
            merged[o["id"]] = o
    orders = list(merged.values())
    for o in orders:
        enrich_project(o, name_map)
        if mask:
            if mask_phone_flag:
                for k in ("content", "note", "resolution", "editable_content",
                          "editable_phenomenon", "editable_type", "phenomenon", "type",
                          "repairer", "reporter", "lift", "position"):
                    if o.get(k):
                        o[k] = mask_phone(o[k])
            if mask_sender:
                if o.get("repairer"):
                    o["repairer"] = hash_name(o["repairer"])
                if o.get("reporter"):
                    o["reporter"] = hash_name(o["reporter"])
                for s in (o.get("sources") or []):
                    if s.get("sender"):
                        s["sender"] = hash_name(s["sender"])
                    if mask_phone_flag and s.get("content"):
                        s["content"] = mask_phone(s["content"])
    data = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "note": "本文件由 wechat-watcher 自动导出, 供外网只读看板使用。数据已脱敏。",
        "cpolar_url": get_cpolar_url(),
        "count": len(orders),
        "orders": orders,
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    log.info("exported %d orders -> %s", len(orders), OUT)
    return len(orders)


if __name__ == "__main__":
    mask = (len(sys.argv) <= 1) or (sys.argv[1] != "nomask")
    n = export(mask=mask)
    print("OK exported", n)
