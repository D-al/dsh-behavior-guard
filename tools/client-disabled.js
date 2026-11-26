// dsh-hardware-monitor 客户端入口 —— 已停用（2026-11-26）
//
// 停用原因：原实现把一个 width:100% + height:100vh 的 iframe 注入到
// `conversation.composer.dock`（对话输入框停靠区，本应放小按钮），
// order:-100 抢占最前，导致整个会话窗口被撑成空白 —— 用户看到的"白屏"。
//
// 原文件备份：D:/Brain/_cleanup_20261118/plugin-repair-20261126/client.js.broken-ui
// 若日后要恢复侧边栏入口，正确做法是注入 `sidebarRight` slot 且组件尺寸受限，
// 不要占用 conversation.composer.dock。
window.__ModuleLoader__.load({
  id: 'dsh-hardware-monitor',
  factory() {
    return {
      inject: [],
      apply() { /* 不注入任何 UI 组件，仅保留模块加载避免报错 */ }
    };
  }
});
