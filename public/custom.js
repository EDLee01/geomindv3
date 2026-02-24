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
  // 2. 添加 Projects 按钮到侧边栏
  // ============================================================
  function addProjectsButton() {
    // 查找侧边栏导航容器
    const sidebar = document.querySelector('[class*="MuiDrawer"] nav, aside nav, [class*="sidebar"] nav');
    if (!sidebar) {
      // 尝试其他选择器
      const drawerContent = document.querySelector('[class*="MuiDrawer-paper"], [class*="drawer"]');
      if (drawerContent) {
        // 查找按钮容器
        const buttonContainer = drawerContent.querySelector('[class*="MuiList"], ul, div > button')?.parentElement;
        if (buttonContainer && !document.getElementById('geomind-projects-btn')) {
          insertProjectsButton(buttonContainer);
        }
      }
      return;
    }

    if (!document.getElementById('geomind-projects-btn')) {
      insertProjectsButton(sidebar);
    }
  }

  function insertProjectsButton(container) {
    // 创建 Projects 按钮
    const projectsBtn = document.createElement('button');
    projectsBtn.id = 'geomind-projects-btn';
    projectsBtn.title = 'Projects - 项目管理';
    projectsBtn.innerHTML = `
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>
        <path d="M12 10v6"/>
        <path d="m9 13 3-3 3 3"/>
      </svg>
    `;
    projectsBtn.style.cssText = `
      display: flex;
      align-items: center;
      justify-content: center;
      width: 40px;
      height: 40px;
      border: none;
      border-radius: 8px;
      background: transparent;
      color: #9ca3af;
      cursor: pointer;
      transition: all 0.2s;
      margin: 4px auto;
    `;

    projectsBtn.onmouseover = function() {
      this.style.background = 'rgba(255,255,255,0.1)';
      this.style.color = '#fff';
    };
    projectsBtn.onmouseout = function() {
      this.style.background = 'transparent';
      this.style.color = '#9ca3af';
    };

    projectsBtn.onclick = function() {
      // 发送 /project list 命令
      const input = document.querySelector('textarea, input[type="text"]');
      if (input) {
        // 模拟输入
        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
        nativeInputValueSetter.call(input, '/project list');
        input.dispatchEvent(new Event('input', { bubbles: true }));

        // 查找发送按钮并点击
        setTimeout(() => {
          const sendBtn = document.querySelector('button[type="submit"], button[class*="send"]');
          if (sendBtn) {
            sendBtn.click();
          } else {
            // 模拟 Enter 键
            input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', bubbles: true }));
          }
        }, 100);
      }
    };

    // 插入到容器
    const firstButton = container.querySelector('button');
    if (firstButton) {
      // 插入到第一个按钮后面
      firstButton.parentNode.insertBefore(projectsBtn, firstButton.nextSibling);
    } else {
      container.appendChild(projectsBtn);
    }

    console.log('[GeoMind] Projects 按钮已添加');
  }

  // 定期检查并添加按钮（因为侧边栏可能是动态加载的）
  setInterval(addProjectsButton, 1000);

  // 初始尝试
  setTimeout(addProjectsButton, 500);

  console.log('[GeoMind] 自定义 JS 已加载');
})();
