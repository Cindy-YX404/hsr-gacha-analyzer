# 崩坏：星穹铁道抽卡概率分析器

Honkai: Star Rail Gacha Analyzer 是一个用于管理个人《崩坏：星穹铁道》账号抽卡记录的本地桌面程序。开发这个程序的目的，是在自己的电脑上长期保存不同 UID 的抽卡历史，查看垫池、五星结果和个人统计，并方便地备份或导出数据。

程序使用原生 Tkinter 窗口，不启动 Web 服务、不依赖浏览器，也不会主动把数据上传到第三方服务器。

程序从官方抽卡记录 API 或本地 JSON/CSV 读取记录，完成分页采集、数据清洗、保底状态建模、统计分析、原生图表展示与多格式导出。

## 桌面版特性

- 原生 Windows 窗口，启动命令为 `python app.py`
- 无 Streamlit、React、Node.js 或数据库服务器
- API 请求、分析、图表和文件导出都在本机完成
- API 获取运行在后台线程，界面不会因分页请求而卡死
- 深蓝星空风界面、左侧数据中心、顶部卡池状态卡和 6 个分析页签
- Matplotlib 图表直接嵌入窗口，不生成网页
- 按 UID 自动合并并保存本地历史，支持多账号切换与恢复上次查看账号
- 支持打包成单文件 `HSR-Gacha-Analyzer.exe`

## 分析功能

- 从官方 `getGachaLog` URL 解析参数并按卡池自动分页
- 网络失败重试、限流退避、空页结束与重复记录去除
- 统一清洗为 pandas DataFrame，并按时间排序
- 支持角色活动、光锥活动、常驻与新手跃迁
- 独立维护角色池 50/50 与光锥池 75/25 的保证状态
- 标注 `UP`、`歪`、`大保底 UP`，常驻池和新手池不显示“歪”
- 支持“天穹之邀”额外非 UP 角色：银狼、希儿、符玄、云璃、刃、银枝
- 计算总抽数、五星/四星数、平均/中位 pity、最早/最晚出金
- 计算当前垫池、历史歪数与非大保底 UP 成功率
- 首页只保留玩家容易理解的星级占比圆环图和各卡池抽数条形图
- 导出 CSV、JSON 和包含 3 个工作表的 Excel
- 内置抽卡链接获取教程和浅灰色 URL 格式示例
- 导入以前导出的 JSON/CSV，默认提供 652 条匿名模拟记录
- 初始模拟数据不包含任何真实角色名或光锥名

## 快速开始

需要 Python 3.11 或更高版本。Tkinter 随标准 Windows Python 一起安装。

```powershell
cd "D:\project\崩铁抽卡分析"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

运行后会直接打开桌面窗口，不会打开浏览器，也没有 localhost 端口。

## 打包成 Windows EXE

项目提供 PyInstaller 配置与一键构建脚本：

```powershell
.\build_exe.ps1
```

构建完成后可直接运行：

```text
dist\HSR-Gacha-Analyzer.exe
```

EXE 会包含示例数据和 banner 配置。目标电脑不需要单独安装 Python。

## 使用真实记录

1. 在游戏抽卡记录页面取得官方 `getGachaLog` 请求 URL。
2. 粘贴到左侧“粘贴抽卡记录链接”输入框。
3. 点击“从 API 获取 / 更新”。
4. 新记录会按 UID 与该账号已有历史自动合并、去重并保存。
5. 获取完成后查看各池状态、五星历史与图表。
6. 使用左侧按钮导出 CSV、Excel 或 JSON。

示例结构只使用占位符：

```text
https://public-operation-hkrpg.mihoyo.com/common/hkrpg_gacha_record/api/getGachaLog?authkey=<YOUR_AUTHKEY>&page=1&size=20&gacha_type=11&end_id=0
```

程序会覆盖分页参数，依次获取配置中支持的四类卡池。请求之间存在节流间隔；临时网络错误会有限次数重试，遇到 429 会等待后再请求。

## 桌面界面

左侧数据中心提供：

- API 链接输入
- 抽卡链接获取教程与 URL 格式提示
- JSON/CSV 导入
- 按 UID 选择本地账号，或切换为“初始数据（隐藏信息）”
- 显示匿名初始数据
- UID、总抽数、五星数和平均出金
- CSV、Excel、JSON 导出

顶部独立显示角色活动跃迁和光锥活动跃迁：

- 当前垫池抽数（70 抽以下为绿色，70 抽及以上为红色）
- “下一金：小保底”或“下一金：大保底”

主区域包含：

- 总览
- 角色活动跃迁
- 光锥活动跃迁
- 常驻跃迁
- 新手跃迁
- 详细记录

活动池五星卡片中的“歪”为红色徽章，“保底”为金色徽章。常驻池和新手池不会显示这些徽章。

## 抽卡规则建模

规则集中在 `config/gacha_rules.py`，常驻五星名单与可扩展 banner metadata 位于 `config/banner_data.json`。

| 卡池 | 硬保底 | 非保证状态下的 UP 概率 | 歪后状态 |
| --- | ---: | ---: | --- |
| 角色活动跃迁 | 90 | 50% | 下一五星必为 UP |
| 光锥活动跃迁 | 80 | 75% | 下一五星必为 UP |
| 常驻跃迁 | 90 | 不适用 | 不适用 |
| 新手跃迁 | 50 | 不适用 | 不适用 |

状态机按时间正序处理每个活动池的五星记录。角色活动池与光锥活动池分别维护 `guaranteed_next`，不会互相影响。

```text
非保证状态 + UP       -> 小保底成功，下一金仍为非保证
非保证状态 + 常驻五星 -> 歪，下一金进入保证状态
保证状态 + UP         -> 大保底，下一金恢复非保证
```

个人“小保底胜率”只统计 `UP / (UP + 歪)`，大保底产生的 UP 不进入分母或分子。

### 如何判断“歪”

API 记录通常只提供物品和卡池字段，不直接提供“是否当期 UP”。MVP 按以下优先级分类：

1. `featured_by_gacha_id` 明确配置为当期 UP：按 UP 处理。
2. 角色活动池五星属于常驻名单，或属于额外非 UP 名单（银狼、希儿、符玄、云璃、刃、银枝）：标记为 `off_banner`。
3. 光锥活动池五星属于常驻五星光锥名单：标记为 `off_banner`。
4. 未配置完整 banner metadata 的其他五星按活动 UP 处理。

常驻池和新手池的 `five_star_result_type` 为 `not_applicable`，不会标记为“歪”。

## 本地数据与安全

- 源码、示例数据和测试中不包含真实 authkey。
- URL 输入框使用密码样式。
- 获取完成后会立即清空 URL 输入框。
- API client 不记录完整 URL；需要展示时会遮盖 authkey。
- authkey 不进入 DataFrame，因此不会进入 CSV、JSON 或 Excel。
- 抽卡明细会按 UID 保存在 `%LOCALAPPDATA%\HSRGachaAnalyzer\accounts\`，用于增量更新和账号切换。
- `settings.json` 只保存上次选择的 UID；重新打开程序时自动恢复该账号。
- 不保存请求 URL、Cookie 或 authkey；账号历史文件仅包含清洗后的抽卡字段。
- 客户端只接受官方 HTTPS API 域名和 `getGachaLog` 路径。
- `.env`、`data/private/`、日志、本地虚拟环境和构建目录已加入 `.gitignore`。

authkey 是临时凭据。不要在截图、Issue、Git 提交或聊天中分享完整链接。

## 项目目的与免责声明

- 本项目仅用于个人账号的抽卡记录整理、本地数据管理和非商业性质的统计分析，不提供抽卡、充值、账号交易或代练服务。
- 本项目是非官方的个人工具，与米哈游、HoYoverse 及其关联公司不存在隶属、合作、赞助、认可或授权关系。
- 《崩坏：星穹铁道》、相关角色名称、游戏术语、商标及其他知识产权归各自权利人所有。本项目不主张对这些内容拥有权利。
- 本项目不包含或分发游戏客户端、角色立绘、音乐、音效、视频等受版权保护的游戏资源；界面只展示 API 返回的文字记录和程序自行生成的统计图表。
- 本项目不会修改游戏客户端、自动执行游戏操作、绕过身份验证或提供作弊功能。用户应遵守游戏用户协议、API 使用规则以及所在地适用的法律法规。
- 抽卡链接中的 authkey 属于临时敏感凭据。用户应只在自己的电脑上使用本人账号生成的链接，不应公开分享或导入来源不明的链接。
- 分析结果取决于 API 当前可返回的历史范围以及本地已有数据，可能因记录缺失、规则调整或卡池配置变化而不完整；游戏内官方记录与说明具有更高优先级。
- 项目使用的 Python 第三方依赖分别适用其各自的开源许可证。

如权利人认为项目中的名称、说明或其他内容存在不当使用，应停止分发相关版本并及时移除或调整有争议的内容。

## Project Architecture

```text
.
├── app.py                         # 原生 Tkinter 桌面 UI
├── build_exe.ps1                  # Windows 一键打包
├── hsr_gacha_analyzer.spec        # PyInstaller 配置
├── config/
│   ├── banner_data.json
│   └── gacha_rules.py
├── data/
│   └── sample_gacha.json
├── scripts/
│   └── generate_sample_data.py
├── src/
│   ├── analyzer.py
│   ├── api_client.py
│   ├── exporter.py
│   ├── parser.py
│   ├── pity.py
│   ├── storage.py
│   └── utils.py
├── tests/
│   ├── test_api_client.py
│   ├── test_desktop_app.py
│   ├── test_exporter.py
│   ├── test_parser.py
│   └── test_pity.py
├── requirements.txt
├── requirements-dev.txt
├── .gitignore
└── README.md
```

### Data Pipeline

```text
Gacha API / JSON / CSV
          ↓
      API Client
          ↓
       Raw JSON
          ↓
        Parser
          ↓
   Clean DataFrame
          ↓
Pity / Guarantee Engine
          ↓
      Analytics
          ↓
 Tkinter Desktop UI
          ↓
CSV / Excel / JSON Export
```

### 模块职责

- `src/api_client.py`：URL 校验、参数解析、分页、重试、限流和 API 错误处理。
- `src/parser.py`：JSON/CSV 导入、字段统一、类型转换、去重和排序。
- `src/pity.py`：pity 计数、常驻名单判断、活动池分类和保证状态机。
- `src/analyzer.py`：账号总览、分池统计、非大保底 UP 成功率和当前状态。
- `src/exporter.py`：内存生成 CSV、JSON 与带样式的三工作表 Excel。
- `src/storage.py`：按 UID 原子保存、增量合并本地历史，并记录上次选择的账号。
- `app.py`：Tkinter 窗口、后台任务、指标卡、五星卡片、表格与 Matplotlib 图表。
- `scripts/generate_sample_data.py`：生成确定性的匿名首次启动模拟数据。

## Technical Decisions

### Tkinter 作为桌面层

Tkinter 是 Python 标准库的一部分，安装成本低，能够直接生成原生窗口。它适合这个个人数据工具的规模，也避免了 Web 服务、浏览器壳或前端构建链。

### Matplotlib 原生嵌入

图表通过 `FigureCanvasTkAgg` 嵌入 Tkinter，所有绘图都在进程内完成，不生成 HTML，也不需要 WebView。

### 后台线程获取 API

分页和退避可能耗时。桌面层只把网络获取放入守护线程；所有 Tkinter 更新仍由主线程执行，避免窗口假死和线程不安全更新。

### DataFrame 作为核心数据层

个人抽卡历史规模较小，pandas 足以完成清洗、聚合和导出。业务模块与桌面 UI 分离，因此将来可以替换界面而不改状态机。

### 配置与逻辑分离

硬保底、基础 UP 概率、卡池映射、常驻五星与额外非 UP 名单均位于 `config/`。游戏规则变化时不需要修改分析代码。

## 测试

```powershell
pip install -r requirements-dev.txt
pytest -q
```

测试覆盖：

- 桌面入口可安全导入，不会在测试时自动打开窗口
- 运行依赖不包含 Streamlit 或 Plotly
- 角色活动池 `UP → 歪 → 大保底 → UP`
- 六名“天穹之邀”限定角色的 off-banner 分类
- 常驻池获得姬子不会标记为歪
- 光锥活动池 `常驻五星 → 大保底 UP`
- 角色池与光锥池保证状态独立
- 大保底不计入个人小保底胜率
- pity 在五星后重置
- 首次启动样例数据的规模、当前垫池和匿名名称约束
- 输入框中的链接示例不会包含真实 authkey
- JSON 结构解析、去重与时间排序
- API 游标分页
- 同 UID 历史增量合并、去重、账号隔离和上次选择恢复
- 三种导出不包含 authkey，Excel 工作表结构正确

也可以执行原生 UI 冒烟检查：

```powershell
python app.py --smoke-test
```

它会创建桌面窗口、加载示例数据、构建全部页签和图表，然后立即退出。

## 数据与规则来源

本项目不隶属于 HoYoverse。规则参数依据游戏内跃迁说明和公开的 HoYoLAB 资料实现，例如 [Version 4.2 Update Details](https://www.hoyolab.com/article/44742273) 对“天穹之邀”可自定义非 UP 角色池的说明、[Version 4.3 Event Warp: Phase II](https://www.hoyolab.com/article_pre/18014398241023179) 对角色活动跃迁独立累计与 50% 机制的说明，以及 [Star Rail New Player Guide](https://www.hoyolab.com/article/20092738) 对常驻 90 抽、光锥活动 80 抽和 75/25 机制的整理。最终应以当前游戏内“跃迁详情”为准。

## Limitations

- 当前结论只基于 API 返回或用户导入的可见历史。若更早记录不可获取，第一枚五星的 pity 和导入起点的保证状态可能未知。
- API 不提供玩家实际选择的“天穹之邀”名单；当前按需求将六名可选限定角色全部视为角色活动池的非 UP 候选。若其中角色作为当期 UP，需要在 `featured_by_gacha_id` 中补充该卡池 metadata。
- 账号历史仅保存在当前电脑，没有登录系统或云同步；重要数据仍建议定期导出备份。
- 没有角色/光锥图片资源，五星历史使用文字卡片与徽章。
- 当前 EXE 配置主要面向 Windows；macOS/Linux 可以直接运行 Python 源码，但需要分别构建安装包。

## Future Improvements

- 维护完整 banner 时间线与 `gacha_id` featured item 映射。
- 支持用户手动声明导入起点的保证状态。
- 在 UI 中配置每个账号实际选择的“天穹之邀”角色。
- 添加 Monte Carlo 抽卡概率模拟。
- 增加角色/光锥本地图片和账号备注名。
- 为 Windows EXE 添加签名、安装器、程序图标和自动更新。
- 添加 GitHub Actions、覆盖率与发布构建。
