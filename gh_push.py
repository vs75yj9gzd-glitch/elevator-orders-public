# -*- coding: utf-8 -*-
"""GitHub 推送层(纯 REST API, 不依赖 git 二进制):

沙箱与本机网络策略常禁 git 直连, 但 GitHub REST API(urllib) 可出网。
本模块用 Git Data API(blob -> tree -> commit -> ref) 推文件,
支持空仓库首次推与后续增量更新(基于 base_tree 保留未变动文件)。

用法:
  gh_push.push_files([("orders.json", "/abs/path/orders.json")], token, user, repo, "msg")
"""
import json
import os
import base64
import urllib.request
import urllib.error
import urllib.parse

API = "https://api.github.com"


def gh_api(method, path, token, data=None, timeout=120):
    url = API + urllib.parse.quote(path, safe="/")
    headers = {"Authorization": "token " + token,
               "Accept": "application/vnd.github+json",
               "User-Agent": "wechat-watcher"}
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, headers=headers, data=body, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace"), r.status
    except urllib.error.HTTPError as e:
        return e.read().decode("utf-8", "replace"), e.code
    except Exception as e:
        return str(e), 0


def put_contents(path, local, token, user, repo, timeout=180):
    """用 Contents API 上传单文件。空仓库时自动创建 main 分支(初始化)。"""
    raw = open(local, "rb").read()
    b64 = base64.b64encode(raw).decode("ascii")
    _, st = gh_api("GET", "/repos/%s/%s/contents/%s" % (user, repo, path), token, timeout=30)
    body = {"message": "add %s" % path, "content": b64}
    if st == 200:
        body["sha"] = json.loads(_)["sha"]
    r, rs = gh_api("PUT", "/repos/%s/%s/contents/%s" % (user, repo, path), token, body, timeout=timeout)
    if rs not in (200, 201):
        raise RuntimeError("put_contents %s fail %s: %s" % (path, rs, r[:200]))
    return rs


def push_files(files, token, user, repo, message, timeout=180):
    """files: list of (path_in_repo, local_abs_path). 返回最终 commit sha。"""
    base_tree_sha = None
    parent_sha = None
    ref_body, st = gh_api("GET", "/repos/%s/%s/git/ref/heads/main" % (user, repo), token, timeout=30)
    if st == 200:
        parent_sha = json.loads(ref_body)["object"]["sha"]
        cmt, _ = gh_api("GET", "/repos/%s/%s/git/commits/%s" % (user, repo, parent_sha), token, timeout=30)
        if cmt and cmt[0] == "{":
            base_tree_sha = json.loads(cmt)["tree"]["sha"]

    tree_items = []
    for rel, lp in files:
        raw = open(lp, "rb").read()
        b64 = base64.b64encode(raw).decode("ascii")
        b, bs = gh_api("POST", "/repos/%s/%s/git/blobs" % (user, repo),
                       token, {"content": b64, "encoding": "base64"}, timeout=timeout)
        if bs != 201:
            raise RuntimeError("blob fail %s (status %s): %s" % (rel, bs, b[:200]))
        tree_items.append({"path": rel, "mode": "100644", "type": "blob", "sha": json.loads(b)["sha"]})

    tree_payload = {"tree": tree_items}
    if base_tree_sha:
        tree_payload["base_tree"] = base_tree_sha
    tb, ts = gh_api("POST", "/repos/%s/%s/git/trees" % (user, repo), token, tree_payload, timeout=timeout)
    if ts != 201:
        raise RuntimeError("tree fail (status %s): %s" % (ts, tb[:200]))
    tree_sha = json.loads(tb)["sha"]

    cmt_payload = {"message": message, "tree": tree_sha}
    if parent_sha:
        cmt_payload["parents"] = [parent_sha]
    cb, cs = gh_api("POST", "/repos/%s/%s/git/commits" % (user, repo), token, cmt_payload, timeout=timeout)
    if cs != 201:
        raise RuntimeError("commit fail (status %s): %s" % (cs, cb[:200]))
    commit_sha = json.loads(cb)["sha"]

    if parent_sha:
        _, rs = gh_api("PATCH", "/repos/%s/%s/git/refs/heads/main" % (user, repo),
                       token, {"sha": commit_sha}, timeout=60)
        if rs not in (200, 201):
            raise RuntimeError("ref update failed status %s" % rs)
    else:
        _, rs = gh_api("POST", "/repos/%s/%s/git/refs" % (user, repo),
                       token, {"ref": "refs/heads/main", "sha": commit_sha}, timeout=60)
        if rs != 201:
            raise RuntimeError("ref create failed status %s" % rs)
    return commit_sha
