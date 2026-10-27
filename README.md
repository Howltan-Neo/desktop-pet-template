# Desktop Pet Template · 可替换角色的 AI 桌宠模板

将小安与小哞项目的 Windows 桌宠、液态玻璃交互面板和制作经验整理为共享运行时。角色外观、动作、台词、点击区域和主题都放在独立角色包里。换角色无需修改程序源码。

**0.1.0 私有验证版。** 已有可运行源码、三个迁移样例、AI 制作命令、逐帧检查工具和 Windows 构建配置。真实桌面验收、真实付费 API 出图与安装包验收的状态见 [验证记录](docs/validation.md)；这些项目不能以源码测试代替。

## 快速运行

使用 Windows 10/11 和包含 Tcl/Tk 的 Python 3.12，从仓库根目录执行：

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe run.py --pack characters/xiaomou
# 或者小安 / 小狗哞：
.venv\Scripts\python.exe run.py --pack characters/xiaoan
.venv\Scripts\python.exe run.py --pack characters/xiaomou-dog
```

创建环境后也可以双击 `Start.cmd`。右键人物打开互动面板；拖动人物播放左右跑动；悬停/点击头部、长按和双击触发角色包指定动作。面板中可选择其他角色包、调整 65%–165% 大小、保持置顶、主动陪伴与停靠位置。托盘可重新显示隐藏的人物。退出通过面板或托盘菜单。

键盘检测只计算匿名按键次数，不保存输入内容；打字时进入工作状态，停止后恢复。鼠标外部左键拖动及“看看你”会使用 16 方向头脸帧。停靠为当前显示器的任务栏保留空间，包括自动隐藏任务栏。人物、对白和所有面板共享置顶设置。

## 制作自己的角色

先准备有权使用的参考图。执行以下命令生成任务书与角色包结构，此步骤离线且不会调用模型：

```powershell
.venv\Scripts\python.exe tools/ai_workflow.py plan my-reference.png characters/my-pet --id my-pet --name 我的桌宠 --constraints "保留原图五官、发型、服装与配饰；自然完整肢体" --accent '#639AB0'
```

你可以将生成的 `AI_TASK.md`、`ai-brief.json` 和参考图交给支持图片生成的 AI 助手，配合本仓库 [AGENTS.md](AGENTS.md) 制作。也可以安装可选 API 依赖，通过自己配置的模型运行生成流程：

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-ai.txt
# 在本地设置 OPENAI_API_KEY；不要写入仓库。
# 将模型名替换为你账户实际可用、支持对应功能的模型。
.venv\Scripts\python.exe tools/ai_workflow.py generate characters/my-pet --text-model YOUR_TEXT_MODEL --image-model YOUR_IMAGE_MODEL --max-images 1
```

生成会先设计动作相位、表情和每个动作至少四条台词，再参考原图与基准帧绘制独立动作帧。默认每次最多一张图；中断后跳过已有帧继续。基准帧确认前请先保持此数量，完整套装会产生多次付费请求。API 默认不自动重试；错误会停止并保留已有文件。普通桌宠运行完全离线，API 仅用于素材制作与视觉评审。具体参数、资料上传范围、修复方式见 [AI 制作流程](docs/ai-workflow.md)。

```powershell
.venv\Scripts\python.exe tools/validate_pack.py characters/my-pet
.venv\Scripts\python.exe tools/qa_pack.py characters/my-pet .qa/my-pet
.venv\Scripts\python.exe tools/ai_workflow.py review characters/my-pet --text-model YOUR_VISION_MODEL
.venv\Scripts\python.exe run.py --pack characters/my-pet
```

程序生成每个动作的逐帧总览、GIF、边界/重复帧提示与哈希；AI 视觉检查会记录具体帧、问题和修复建议。动作真实性、人物一致性及绘画完整性仍需查看参考图、全部动作循环与真实应用。机器或模型“通过”不会自动变成人工验收。

## 自定义主题与互动

修改角色包的 `character.json` 即可配置动作帧数、帧率、台词、热区和主题；默认保留现有玻璃风格与霞鹜字体。支持包内自定义字体。小安默认蓝灰，小哞默认暖鹅黄。格式、方向顺序与事件说明见 [角色包规范](docs/character-pack.md)。

角色包样例用于当前私有验证，原有人物图像不随代码 MIT 许可开放。复制模板给其他人之前，请换成自己有权使用的角色素材，并保留字体与依赖许可，详见 [第三方与素材说明](THIRD_PARTY.md)。

## 检查与构建

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe run.py --pack characters/xiaoan --check
.venv\Scripts\python.exe tools/render_preview.py characters/xiaoan .qa/ui/xiaoan
.venv\Scripts\python.exe tools/smoke_windows.py characters/xiaoan .qa/smoke/xiaoan
.\build.ps1 -PythonExe .venv\Scripts\python.exe
# 可选：本机安装 Inno Setup 后传入 ISCC.exe 路径构建安装器。
```

GitHub Actions 提供 Windows 检查与手动构建流程。Windows 桌面运行时仅支持 Windows；角色包工具和离线测试可在其他支持 Pillow 的平台使用。AI 流程测试使用模拟客户端，不产生费用。模板当前不包含小安原项目的 Codex 日志读取与授权 Hook；它们不是角色替换所必需的能力，后续应作为独立的可选集成加入。
