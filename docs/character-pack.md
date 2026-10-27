# 角色包规范 v1

角色包是用户控制的目录，包含 `character.json`、PNG 动画帧与可选字体。路径相对于角色包根目录，不允许绝对路径或逃逸到包外。原始参考图不需要放入角色包，可由制作者自行保留。

```json
{
  "schema_version": 1,
  "id": "my-character",
  "name": "我的角色",
  "canvas": [512, 512],
  "theme": {"accent": "#C28B45", "font": null},
  "actions": {
    "idle": {"label": "待机", "frames": ["frames/idle/00.png", "frames/idle/01.png"], "fps": 2, "dialogue": ["我在这里。"]}
  }
}
```

`id` 使用小写英文字母、数字及连字符，各角色使用独立 ID，以隔离设置与单实例锁。名称与按钮 label 最多 24 字符，建议名称 8 字符内、标签 6 汉字内。只有 idle 必需；以上示例需要补齐实际 PNG 后才能运行。建议采用方形 512×512，运行时会把其他尺寸缩放到方形。

所有帧为与画布尺寸一致的 RGBA PNG。动作各自配置帧数、fps 和 dialogue；常规动作建议 5–6 帧以上，跑步 8 帧。`look_direction` 若提供必须恰好 16 帧，0 向上，之后每 22.5 度顺时针一帧，并绘制真实头脸朝向变化。

内置语义包括 wave、pet_left、pet_front、pet_right、pet_rub、run_left、run_right、work、waiting、thinking 等。可用顶层 `aliases` 对象将缺少的语义动作映射至已有动作，例如 `{"pet_left":"pet_front"}`。未映射的缺失动作回退 idle。自定义动作自动进入全部动作面板。

顶层 `hotzones` 数组格式为 `[{"rect":[100,30,410,240],"action":"pet_front"}]`，坐标归一化为 512×512，按数组顺序匹配，并与动作的透明轮廓取交集。头部悬停/长按针对 pet_ 前缀动作；其他角色特有部件用其真实位置和动作配置，不沿用别人的耳朵、头发或尾巴坐标。

顶层 `interactions` 支持 click、double_click、hold 对应动作，以及 keyboard、mouse_gaze 布尔开关和 ambient 动作数组。例如 `{"click":"wave","double_click":"stretch","hold":"pet_rub","keyboard":true,"mouse_gaze":true,"ambient":["waiting","yawn"]}`。引用的动作必须存在；至少约 10 分钟无互动才触发 ambient。手动交互优先于键盘工作状态。禁用主动陪伴会停止键盘和随机自动动作；鼠标跟随由 mouse_gaze 控制。

主题 theme 支持 accent、ink、muted、surface 四项 #RRGGBB 配色。font=null 使用附带字体；自定义为包内字体相对路径并保留授权。messages 可自定义 subtitle（面板副标题）和 dock（停靠对白）。玻璃为桌面取样、模糊与透明色键轮廓的近似，每约 1.8 秒刷新，并非系统原生逐像素 Liquid Glass。

默认保留原项目的头部悬停、按下和身体轻点光标。可选顶层 cursors 对象的 head、head_pressed、body 字段可指向角色包内的 .cur 文件。加载失败会回退标准手形，避免路径兼容性问题阻止应用启动。

制作流程应保留参考图和确认过的基准帧，记录形象约束；逐动作生成独立帧、循环预览和对话，再检查身份特征、五官、衣服、肢体、透明边缘、基线和首尾衔接。验收应包含用户实际看到的动图及 Windows 应用。AI 的视觉审查和自动图像检查仅提供线索，不是可靠的自然度证明。用图像或 AI 服务前应由使用者选择提供商并明确知悉上传及费用。
