# AI 制作、审查与修复

`tools/ai_workflow.py plan` 离线保存原始参考、哈希、人物约束、17 个动作的逐帧输出路径和 AI_TASK.md。可交给支持图像生成的 AI 助手执行，也可使用下面的 API 命令。人物专属附加动作可自行加入 character.json；耳朵或尾巴等部件只能在参考中确实存在时加入。

API 方式使用官方 OpenAI Python SDK 和 Responses API，模型名必须显式指定。图像模型需要支持带参考图编辑、透明 PNG；文本模型需要支持图像输入，生成时还需支持 image_generation 工具。接口参考：[图像生成官方文档](https://developers.openai.com/api/docs/guides/image-generation)。不同账户的可用模型与额度不同；模板不固定价格或保证某个模型账户可用。

运行 generate/review 时，参考图、人物约束和指定动作的图像会发送至所配置的服务；密钥只从本地环境变量 OPENAI_API_KEY 读取。普通桌宠运行不联网。本仓库不会自动寻找或读取其他应用密钥。

## 顺序

1. 执行 plan。检查 reference.png 和 ai-brief.json，准确填写五官、发型、服装、配饰、手脚与禁止改变的细节。
2. 第一次 generate 保持 `--max-images 1`，先绘制 idle 的 00 帧。此阶段会设计全部所选动作的相位和台词，并保存 ai-design.json。打开基准帧与原图比较，确认后再继续；模板不会声称已获得人的确认。
3. 继续 generate。默认跳过已经存在的帧，每次有明确的图片数量上限。每个请求参考原图和已经存在的基准帧，原始生成保存在 generated-originals，尺寸统一后的透明帧进入 frames。
4. 执行 validate_pack 与 qa_pack，逐个查看动作总览与 GIF。结构检查会检测缺文件、尺寸、透明通道和无效配置；QA 会报告重复图像、边界接触和哈希。
5. 执行 review，由视觉模型对照参考图与有序帧，记录具体帧、身份一致性、表情、身体完整性、穿插、遮挡、边界、重影、基线和循环衔接问题。ai-review.json 记录对应帧哈希，改变帧后旧结论不能作为新验收。
6. 定点修复，再次审查，最后在 Windows 应用中验证交互、方向和尺寸。

```powershell
python tools/ai_workflow.py generate characters/my-pet --text-model YOUR_TEXT_MODEL --image-model YOUR_IMAGE_MODEL --max-images 1 --action wave --repair --frame 2
python tools/ai_workflow.py review characters/my-pet --text-model YOUR_VISION_MODEL --action wave
```

修复明确指定 action 和 frame，旧帧会按哈希保存在 previous-frames。默认不自动重试付费请求；请求失败后停止并保留完成的内容。网络超时后无法保证服务端未计费，重新执行前应查看提供商记录。只有有意义的姿态变化才算动作，不能以整张图的缩放、平移或复制凑帧数。

当前自动生成可设计动作相位、逐帧绘制、表情细节与中文台词，但不保证一次生成即可达到成品标准。视觉模型能辅助发现问题，无法可靠证明动作真实或不存在绘画错误。缺少真人逐帧及应用验收时，应保留 pending 状态。
