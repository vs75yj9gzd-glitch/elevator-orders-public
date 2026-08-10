// C2 方案 (GitHub + jsDelivr) 部署时修改这里:
// 1. DATA_URL 改成你的仓库: https://cdn.jsdelivr.net/gh/<你的GitHub用户名>/<仓库名>@main/orders.json
// 2. CLOSE_TOKEN / EDIT_TOKEN 与内网 app.py 的一致 (用于外网「标记完成/编辑」写回内网)
// 3. WATCHED_GROUPS: 本机监控群列表, 只显示这些项目导航(空数组=显示全部)
// 注意: 写操作在外网首次使用时, 会提示输入内网访问口令(访问口令不写进本文件, 只存浏览器本地)
window.APP_CONFIG = {
  DATA_MODE: "github",
  DATA_URL: "https://cdn.jsdelivr.net/gh/vs75yj9gzd-glitch/elevator-orders-public@main/orders.json",
  CPOLAR_FALLBACK: "",
  CLOSE_TOKEN: "7d2e9a1c4b6f8e30a5c7d9b2e4f6a8c10b3d5e7f92468ace0",
  EDIT_TOKEN: "a3f9c2e7b4d18a6f5e20c9b37d4816af2b5e9c0d74f3a1b8",
  WATCHED_GROUPS: [
    "盛天小世界电梯维保报修群",
    "盛天国际电梯维保群",
    "绿城盛尧电梯维保沟通群",
    "盛天公馆电梯维保维修工作群",
    "东郡盛天商业维保交流群",
    "盛天东郡电梯报修群",
    "果岭电梯维保群",
    "盛天天天天天报修群"
  ]
}
