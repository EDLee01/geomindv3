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
    try {
      // 如果已存在，跳过
      if (document.getElementById('geomind-projects-btn')) {
        return;
      }

      // 创建浮动按钮 - 放在右下角更明显
      const btn = document.createElement('button');
      btn.id = 'geomind-projects-btn';
      btn.title = 'Projects - 点击管理项目';
      btn.innerHTML = '📁';
      btn.style.cssText = `
        position: fixed !important;
        bottom: 100px !important;
        right: 20px !important;
        z-index: 99999 !important;
        width: 48px !important;
        height: 48px !important;
        border: none !important;
        border-radius: 50% !important;
        background: #6366f1 !important;
        color: white !important;
        font-size: 22px !important;
        cursor: pointer !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.4) !important;
        transition: all 0.2s ease !important;
        visibility: visible !important;
        opacity: 1 !important;
      `;

      btn.onmouseover = function() {
        this.style.transform = 'scale(1.1)';
        this.style.boxShadow = '0 6px 16px rgba(0,0,0,0.5)';
      };
      btn.onmouseout = function() {
        this.style.transform = 'scale(1)';
        this.style.boxShadow = '0 4px 12px rgba(0,0,0,0.4)';
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
        } else {
          console.warn('[GeoMind] 找不到输入框');
        }
      };

      document.body.appendChild(btn);
      console.log('[GeoMind] Projects 按钮已添加到页面');
    } catch (err) {
      console.error('[GeoMind] 添加按钮失败:', err);
    }
  }

  // 多次尝试添加按钮
  function ensureButton() {
    addProjectsButton();
    // 再次检查
    setTimeout(() => {
      if (!document.getElementById('geomind-projects-btn')) {
        console.log('[GeoMind] 按钮不存在，重试...');
        addProjectsButton();
      }
    }, 2000);
  }

  // 页面加载后添加按钮
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => setTimeout(ensureButton, 1000));
  } else {
    setTimeout(ensureButton, 1000);
  }

  // 路由变化时重新添加
  let lastUrl = location.href;
  setInterval(() => {
    const btn = document.getElementById('geomind-projects-btn');
    if (!btn) {
      addProjectsButton();
    }
    if (location.href !== lastUrl) {
      lastUrl = location.href;
      setTimeout(addProjectsButton, 500);
    }
  }, 2000);

  console.log('[GeoMind] 自定义 JS 已加载');
})();
