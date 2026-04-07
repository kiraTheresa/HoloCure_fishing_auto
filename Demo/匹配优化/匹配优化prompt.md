你需要在现有 OpenCV 模板匹配代码基础上进行增强优化，目标是在不引入深度学习的前提下，提高在“多目标 + 动态噪声（如下雨）”场景下的稳定性与准确性。

请严格按以下要求修改代码：

***

# 一、整体目标

当前系统问题：

- ROI 中可能同时存在多个目标（最多约 4 个）
- 存在动态噪声（如下雨粒子）
- 当前只取 Top-1 匹配，容易误判

优化目标：

1. 提升抗噪能力
2. 支持多候选（Top-K）
3. 利用“目标只向右移动”的时序规律减少干扰

***

# 二、功能改造要求

## 1️⃣ 降噪 + 边缘匹配（必须实现）

在模板匹配前，对 ROI 做如下处理：

### (1) 高斯模糊（去雨滴噪声）

```python
roi_blur = cv2.GaussianBlur(roi_gray, (5, 5), 0)
```

### (2) Canny 边缘检测

```python
roi_edge = cv2.Canny(roi_blur, 50, 150)
```

***

### (3) 模板也要做同样处理（重点！）

在 load\_templates 时增加：

```python
tpl_blur = cv2.GaussianBlur(tpl, (5, 5), 0)
tpl_edge = cv2.Canny(tpl_blur, 50, 150)
```

最终用于匹配的是：

```python
roi_edge vs tpl_edge
```

***

## 2️⃣ Top-K 匹配（K=5）

替换当前“只取 max\_val”的逻辑：

### 修改 match\_templates：

要求：

- 对每个模板获取 result map
- 不只取 max，而是取前 K=5 个高分点

实现方式（建议）：

```python
K = 5
flat = result.flatten()
indices = np.argpartition(flat, -K)[-K:]
indices = indices[np.argsort(-flat[indices])]
```

转换为二维坐标：

```python
h, w = result.shape
candidates = [(idx % w, idx // w, flat[idx]) for idx in indices]
```

***

### 输出结构修改为：

```python
[
    {
        "name": template_name,
        "score": score,
        "loc": (x, y)
    },
    ...
]
```

最终返回：

```python
top_candidates  # 全模板混合排序后的前5个
```

***

## 3️⃣ 引入“预测位置窗口”（核心优化）

利用以下先验：

- 目标只会从左向右移动
- 速度不固定

***

### 新增全局变量：

```python
last_x = None
SEARCH_MARGIN = 80  # 可调
```

***

### 在 ROI 内只搜索局部区域：

如果 last\_x 存在：

```python
x_start = max(0, last_x - SEARCH_MARGIN)
x_end   = min(roi_width, last_x + SEARCH_MARGIN)
roi_crop = roi_edge[:, x_start:x_end]
```

匹配时用 roi\_crop，而不是整个 ROI

***

### 坐标修正（非常重要）：

匹配得到的位置需要加回偏移：

```python
real_x = match_x + x_start
```

***

### 更新 last\_x：

从 Top-K 中选择：

```python
选择 score 最高的候选
更新 last_x = 该候选的 x
```

***

## 4️⃣ 多目标输出（可视化）

在 ROI 上绘制 Top-K：

```python
for c in candidates:
    cv2.rectangle(...)
    cv2.putText(...)
```

显示：

```text
name + score
```

***

# 三、决策逻辑优化

当前逻辑：

```python
只取 best_val >= threshold
```

改为：

### 新策略：

1. 取 Top-K
2. 过滤：
   - score >= 0.6（可调）
3. 按 score 排序
4. 取第一个作为主结果
5. 保留其余作为候选（用于调试）

***

# 四、性能要求

必须保证：

- 实时运行（>= 30 FPS）
- 不显著增加计算量

优化建议：

- ROI 已经很小，可以接受 Top-K
- 边缘检测比原始匹配更稳定

***

# 五、输出日志（必须）

每帧输出：

```text
[Top-K]
1. up    0.91 (x,y)
2. left  0.88 (x,y)
...
```

***

# 六、代码风格要求

- 保持现有结构（不要重写 main）
- 新增函数优先
- 不破坏原有接口
- 所有新参数写在顶部（可调）

***

# 七、最终效果预期

优化后系统应具备：

- 对雨滴噪声不敏感
- 多目标情况下不误判
- 识别稳定（无频繁跳变）
- 利用运动规律提高精度

***

只输出完整可运行代码，不要解释。
