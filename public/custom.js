// GeoMind 自定义 JS
(function() {
  // ============================================================
  // 1. 修复新对话弹窗文字
  // ============================================================
  const observer = new MutationObserver(function(mutations) {
    mutations.forEach(function(mutation) {
      mutation.addedNodes.forEach(function(node) {
        if (node.nodeType === 1) {
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

  observer.observe(document.body, {
    childList: true,
    subtree: true
  });

  // ============================================================
  // 2. 添加 Projects 浮动按钮（固定位置，更可靠）
  // ============================================================
  function addProjectsButton() {
    if (document.getElementById('geomind-projects-btn')) {
      return;
    }

    // 创建浮动按钮
    const btn = document.createElement('button');
    btn.id = 'geomind-projects-btn';
    btn.title = '📁 Projects - 点击管理项目';
    btn.innerHTML = '📁';
    btn.style.cssText = `
      position: fixed;
      top: 12px;
      left: 60px;
      z-index: 9999;
      width: 36px;
      height: 36px;
      border: none;
      border-radius: 8px;
      background: rgba(99, 102, 241, 0.9);
      color: white;
      font-size: 18px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 2px 8px rgba(0,0,0,0.3);
      transition: all 0.2s ease;
    `;

    btn.onmouseover = function() {
      this.style.transform = 'scale(1.1)';
      this.style.background = 'rgba(99, 102, 241, 1)';
    };
    btn.onmouseout = function() {
      this.style.transform = 'scale(1)';
      this.style.background = 'rgba(99, 102, 241, 0.9)';
    };

    btn.onclick = function(e) {
      e.preventDefault();
      e.stopPropagation();

      // 发送 /project list 命令
      const textarea = document.querySelector('textarea');
      if (textarea) {
        textarea.value = '/project list';
        textarea.dispatchEvent(new Event('input', { bubbles: true }));

        // 触发表单提交
        setTimeout(() => {
          const form = textarea.closest('form');
          if (form) {
            form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
          }
          // 备用：按 Enter
          textarea.dispatchEvent(new KeyboardEvent('keydown', {
            key: 'Enter',
            code: 'Enter',
            keyCode: 13,
            which: 13,
            bubbles: true
          }));
        }, 100);
      }
    };

    document.body.appendChild(btn);
    console.log('[GeoMind] Projects 按钮已添加');
  }

  // 页面加载后添加按钮
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => setTimeout(addProjectsButton, 500));
  } else {
    setTimeout(addProjectsButton, 500);
  }

  // 路由变化时重新添加
  let lastUrl = location.href;
  setInterval(() => {
    if (location.href !== lastUrl) {
      lastUrl = location.href;
      setTimeout(addProjectsButton, 500);
    }
  }, 1000);

  console.log('[GeoMind] 自定义 JS 已加载');
})();
