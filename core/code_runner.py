"""
GeoMind Core - Python 代码执行器
自动执行 → 检查结果 → 失败则修代码重试（最多 3 轮）

功能：
- 自动检测并安装缺失的依赖库
- 支持将上传文件复制到执行目录
"""

import subprocess
import tempfile
import base64
import re
import sys
import shutil
from pathlib import Path
from typing import Dict, List, Optional


# ============================================================
# 依赖库自动安装
# ============================================================

# 常见 import 名 -> pip 包名 映射
IMPORT_TO_PACKAGE = {
    "sklearn": "scikit-learn",
    "cv2": "opencv-python",
    "PIL": "Pillow",
    "skimage": "scikit-image",
}


def detect_missing_module(error: str) -> Optional[str]:
    """
    从错误信息中检测缺失的模块名

    Returns:
        模块名（如果是 ModuleNotFoundError），否则返回 None
    """
    patterns = [
        r"ModuleNotFoundError: No module named ['\"]([^'\"]+)['\"]",
        r"ImportError: No module named ['\"]([^'\"]+)['\"]",
    ]
    for pattern in patterns:
        match = re.search(pattern, error)
        if match:
            module = match.group(1).split(".")[0]  # 取顶层模块名
            return module
    return None


def install_package(module_name: str) -> Dict:
    """
    使用 pip 安装缺失的包

    Args:
        module_name: 模块名

    Returns:
        {"success": bool, "message": str}
    """
    # 转换为 pip 包名
    package_name = IMPORT_TO_PACKAGE.get(module_name, module_name)

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", package_name],
            capture_output=True,
            text=True,
            timeout=120,  # 安装超时 2 分钟
        )

        if result.returncode == 0:
            return {"success": True, "message": f"✅ 已自动安装: {package_name}"}
        else:
            return {"success": False, "message": f"❌ 安装失败: {result.stderr[:500]}"}

    except subprocess.TimeoutExpired:
        return {"success": False, "message": f"❌ 安装超时: {package_name}"}
    except Exception as e:
        return {"success": False, "message": f"❌ 安装错误: {str(e)}"}


# ============================================================
# 代码执行
# ============================================================

# matplotlib 初始化代码（自动注入到每个脚本开头）
MATPLOTLIB_SETUP = """
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

# 中文字体尝试
try:
    plt.rcParams['font.sans-serif'] = ['SimHei', 'WenQuanYi Micro Hei', 'DejaVu Sans']
except:
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
"""


def execute_python(
    code: str,
    timeout: int = 30,
    work_dir: str = None,
    uploaded_files: List[Dict] = None,
    auto_install: bool = True,
) -> Dict:
    """
    执行 Python 代码

    Args:
        code: Python 代码字符串
        timeout: 超时秒数
        work_dir: 工作目录（可选，默认临时目录）
        uploaded_files: 上传的文件列表 [{"name": "xxx.xlsx", "path": "/tmp/xxx"}]
        auto_install: 是否自动安装缺失的依赖（默认 True）

    Returns:
        {
            "success": bool,
            "output": str,       # stdout
            "error": str | None, # stderr（失败时）
            "images": [          # matplotlib 生成的图片
                {"filename": "xxx.png", "data": "base64..."}
            ],
            "installed": [str]   # 自动安装的包列表
        }
    """
    result = {"success": False, "output": "", "error": None, "images": [], "installed": []}

    try:
        # 创建临时目录（或使用指定目录）
        if work_dir:
            tmpdir = work_dir
            Path(tmpdir).mkdir(parents=True, exist_ok=True)
            cleanup = False
        else:
            _tmpdir_obj = tempfile.TemporaryDirectory()
            tmpdir = _tmpdir_obj.name
            cleanup = True

        try:
            # 复制上传的文件到执行目录
            if uploaded_files:
                for f in uploaded_files:
                    src_path = Path(f["path"])
                    if src_path.exists():
                        dst_path = Path(tmpdir) / f["name"]
                        shutil.copy2(src_path, dst_path)

            # 注入 matplotlib 配置 + 用户代码
            full_code = MATPLOTLIB_SETUP + "\n" + code

            code_file = Path(tmpdir) / "script.py"
            code_file.write_text(full_code, encoding="utf-8")

            # 执行代码（支持自动安装依赖重试）
            max_install_retries = 3
            install_retries = 0

            while install_retries <= max_install_retries:
                proc = subprocess.run(
                    [sys.executable, str(code_file)],
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )

                result["output"] = proc.stdout.strip()
                result["success"] = proc.returncode == 0

                if proc.returncode != 0:
                    stderr = proc.stderr.strip()
                    result["error"] = stderr

                    # 检测是否是缺失模块错误
                    if auto_install and install_retries < max_install_retries:
                        missing_module = detect_missing_module(stderr)
                        if missing_module:
                            install_result = install_package(missing_module)
                            if install_result["success"]:
                                result["installed"].append(missing_module)
                                install_retries += 1
                                continue  # 安装成功，重试执行

                    break  # 不是模块缺失或安装失败，退出循环
                else:
                    break  # 执行成功，退出循环

            # 收集生成的图片
            for img_file in sorted(Path(tmpdir).glob("*.png")):
                with open(img_file, "rb") as f:
                    img_data = base64.b64encode(f.read()).decode()
                    result["images"].append(
                        {"filename": img_file.name, "data": img_data}
                    )

        finally:
            if cleanup:
                _tmpdir_obj.cleanup()

    except subprocess.TimeoutExpired:
        result["error"] = f"⏰ 执行超时 ({timeout}秒限制)"
    except Exception as e:
        result["error"] = f"系统错误: {str(e)}"

    return result


# ============================================================
# 代码提取
# ============================================================

def extract_code_blocks(text: str) -> List[str]:
    """从 AI 回复中提取 Python 代码块"""
    pattern = r"```python\s*\n(.*?)\n```"
    blocks = re.findall(pattern, text, re.DOTALL)
    return [b.strip() for b in blocks if b.strip()]


def extract_markdown_blocks(text: str) -> List[str]:
    """从 AI 回复中提取 Markdown 文档块"""
    pattern = r"```markdown\s*\n(.*?)\n```"
    blocks = re.findall(pattern, text, re.DOTALL)
    return [b.strip() for b in blocks if b.strip()]


# ============================================================
# 执行结果格式化
# ============================================================

def format_execution_result(result: Dict) -> str:
    """将执行结果格式化为用户可读文本"""
    parts = []

    if result["success"]:
        parts.append("✅ **代码执行成功**")
        if result["output"]:
            parts.append(f"```\n{result['output']}\n```")
        if result["images"]:
            parts.append(f"📊 生成了 {len(result['images'])} 张图表")
    else:
        parts.append("❌ **代码执行失败**")
        if result["error"]:
            # 截取关键错误信息
            error_lines = result["error"].split("\n")
            # 只保留最后几行（通常是最有用的错误信息）
            key_errors = error_lines[-5:] if len(error_lines) > 5 else error_lines
            parts.append(f"```\n{chr(10).join(key_errors)}\n```")

    return "\n\n".join(parts)


def build_fix_prompt(code: str, error: str) -> str:
    """构建让 AI 修复代码的提示"""
    return f"""上面的 Python 代码执行失败了。

**错误信息：**
```
{error}
```

**原始代码：**
```python
{code}
```

请修复这个错误，给出完整的修正后代码。注意：
1. 将修正后的代码放在 ```python 代码块中
2. 确保代码可以独立运行
3. 图表使用 plt.savefig('output.png') 保存
4. 用 print() 输出数值结果
"""
