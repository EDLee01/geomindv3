// GeoMind 自定义 JS - 修复新对话弹窗文字
(function() {
  // 监听 DOM 变化，当弹窗出现时修改文字
  const observer = new MutationObserver(function(mutations) {
    mutations.forEach(function(mutation) {
      mutation.addedNodes.forEach(function(node) {
        if (node.nodeType === 1) {
          // 查找弹窗标题和描述
          const dialogTitle = node.querySelector && node.querySelector('[class*="MuiDialogTitle"], [class*="DialogTitle"]');
          const dialogContent = node.querySelector && node.querySelector('[class*="MuiDialogContent"], [class*="DialogContent"]');

          if (dialogTitle && dialogTitle.textContent.includes('创建新对话')) {
            dialogTitle.textContent = '开始新对话？';
          }

          if (dialogContent) {
            const description = dialogContent.querySelector('p, [class*="Typography"]');
            if (description && description.textContent.includes('清除')) {
              description.textContent = '当前对话会保存在左侧历史记录中。';
            }
          }

          // 也检查子元素
          const allText = node.querySelectorAll && node.querySelectorAll('p, span, div, h2, h3');
          if (allText) {
            allText.forEach(function(el) {
              if (el.textContent === '创建新对话') {
                el.textContent = '开始新对话？';
              }
              if (el.textContent.includes('这将清除您当前的聊天记录')) {
                el.textContent = '当前对话会保存在左侧历史记录中。';
              }
            });
          }
        }
      });
    });
  });

  // 开始监听
  observer.observe(document.body, {
    childList: true,
    subtree: true
  });

  console.log('[GeoMind] 自定义 JS 已加载');
})();
