# PDF 内容提取

## 触发词
- PDF
- 提取PDF
- 读取PDF
- 解析PDF
- PDF内容

## 能力描述
从用户上传的 PDF 文件中提取指定内容，支持：
- 提取全文文本
- 提取指定页码内容
- 提取表格数据
- 提取图片描述
- 按关键词搜索内容

## 执行流程

### 1. 确认需求
询问用户：
- 需要提取哪些内容（全文/指定页/表格/关键词搜索）
- 如果是指定页，询问页码范围
- 如果是关键词搜索，询问关键词

### 2. 生成提取代码
根据需求生成 Python 代码，使用以下库：

```python
# 方案1: PyMuPDF (推荐，功能全面)
import fitz  # pip install PyMuPDF

# 打开 PDF
doc = fitz.open("filename.pdf")

# 提取全文
text = ""
for page in doc:
    text += page.get_text()

# 提取指定页 (页码从0开始)
page = doc[0]  # 第1页
text = page.get_text()

# 提取表格
tables = page.find_tables()
for table in tables:
    df = table.to_pandas()
    print(df)

# 搜索关键词
for page_num, page in enumerate(doc):
    results = page.search_for("关键词")
    if results:
        print(f"第{page_num+1}页找到 {len(results)} 处")
```

```python
# 方案2: pdfplumber (表格提取更好)
import pdfplumber  # pip install pdfplumber

with pdfplumber.open("filename.pdf") as pdf:
    # 提取全文
    for page in pdf.pages:
        text = page.extract_text()
        print(text)

    # 提取表格
    for page in pdf.pages:
        tables = page.extract_tables()
        for table in tables:
            print(table)
```

### 3. 输出格式
- 文本内容：直接输出或保存为 .txt
- 表格数据：转换为 DataFrame 并显示/导出 CSV
- 搜索结果：显示页码和上下文

## 注意事项
1. 确保用户已上传 PDF 文件
2. 大文件可能需要分页处理
3. 扫描版 PDF 需要 OCR（提示用户）
4. 加密 PDF 需要密码

## 示例对话

用户: 帮我提取这个PDF的第3-5页内容
助手: 好的，我来提取 PDF 第3-5页的内容。

```python
import fitz

doc = fitz.open("your_file.pdf")
text = ""
for i in range(2, 5):  # 页码从0开始，所以3-5页是索引2-4
    if i < len(doc):
        text += f"\n=== 第{i+1}页 ===\n"
        text += doc[i].get_text()

print(text)
```
