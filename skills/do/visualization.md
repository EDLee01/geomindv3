# 可视化 (Visualization)

## 触发条件
- "画图" "图表" "可视化" "生成图" "visualization" "plot" "chart"

## 配置
- 分辨率: 300 dpi
- 字体: SimHei (中文) + Times New Roman (英文)
- 配色: 学术风格（蓝-绿-橙色系）

## 图表类型
- 折线图、散点图、柱状图、箱线图
- 热力图、等值线图
- 组合图（双 Y 轴）
- 子图排列

## 代码模板
```python
import matplotlib.pyplot as plt
import numpy as np

fig, ax = plt.subplots(figsize=(10, 6))
# ... 绑图代码 ...
plt.savefig('output.png', dpi=300, bbox_inches='tight')
print('图表已生成')
```

## 注意事项
- 必须包含轴标签和标题
- 图例清晰可读
- 色彩对比度足够
