from pathlib import Path

from win32com.client import DispatchEx


ROOT = Path(r"E:\codex")
PPT_PATH = ROOT / "小手变形画_幼教风格课件_规范版.pptx"
SLIDE_W = 960
SLIDE_H = 540


def rgb(r, g, b):
    return r + (g << 8) + (b << 16)


COLORS = {
    "yellow": rgb(255, 209, 56),
    "blue": rgb(199, 230, 249),
    "cream": rgb(255, 247, 232),
    "white": rgb(255, 255, 255),
    "text": rgb(64, 64, 64),
    "muted": rgb(108, 108, 108),
    "orange": rgb(255, 166, 44),
    "pink": rgb(255, 232, 238),
    "green": rgb(232, 248, 227),
    "light_blue": rgb(228, 241, 252),
    "line": rgb(90, 90, 90),
    "accent_blue": rgb(92, 171, 243),
    "accent_green": rgb(133, 201, 96),
    "accent_pink": rgb(245, 125, 150),
}


def add_shape(slide, kind, left, top, width, height, fill, line=None, weight=1.5):
    shp = slide.Shapes.AddShape(kind, left, top, width, height)
    shp.Fill.ForeColor.RGB = fill
    shp.Line.ForeColor.RGB = line if line is not None else fill
    shp.Line.Weight = weight
    return shp


def add_text(slide, left, top, width, height, text, size=24, color=None, bold=False, align=1):
    tb = slide.Shapes.AddTextbox(1, left, top, width, height)
    tr = tb.TextFrame.TextRange
    tr.Text = text
    tr.Font.NameFarEast = "微软雅黑"
    tr.Font.Name = "微软雅黑"
    tr.Font.Size = size
    tr.Font.Bold = -1 if bold else 0
    tr.Font.Color.RGB = color or COLORS["text"]
    tr.ParagraphFormat.Alignment = align
    tb.TextFrame.WordWrap = -1
    return tb


def bg(slide, color):
    add_shape(slide, 1, 0, 0, SLIDE_W, SLIDE_H, color, color, 0)


def title_row(slide, tag, title):
    add_shape(slide, 5, 62, 28, 120, 34, COLORS["orange"], COLORS["orange"])
    add_text(slide, 79, 34, 86, 20, tag, size=17, color=COLORS["white"], bold=True, align=2)
    add_text(slide, 200, 29, 360, 30, title, size=28, bold=True)


def card(slide, left, top, width, height, fill=COLORS["white"]):
    return add_shape(slide, 5, left, top, width, height, fill, fill, 1)


def bullet_block(slide, left, top, width, height, lines, size=21, color=None):
    text = "\r".join([f"• {line}" for line in lines])
    add_text(slide, left, top, width, height, text, size=size, color=color or COLORS["text"])


def build():
    app = DispatchEx("PowerPoint.Application")
    app.Visible = 1
    app.DisplayAlerts = 0

    presentation = app.Presentations.Add()
    presentation.PageSetup.SlideWidth = SLIDE_W
    presentation.PageSetup.SlideHeight = SLIDE_H

    for i in range(1, presentation.Slides.Count + 1):
        presentation.Slides(i).Delete()

    def slide():
        return presentation.Slides.Add(presentation.Slides.Count + 1, 12)

    s1 = slide()
    bg(s1, COLORS["blue"])
    add_shape(s1, 9, -20, -8, 230, 90, COLORS["cream"], COLORS["cream"], 0)
    add_shape(s1, 9, 760, -12, 240, 110, COLORS["cream"], COLORS["cream"], 0)
    add_shape(s1, 9, -25, 455, 220, 100, COLORS["pink"], COLORS["pink"], 0)
    add_shape(s1, 9, 760, 448, 230, 110, COLORS["green"], COLORS["green"], 0)
    add_shape(s1, 5, 92, 58, 776, 400, COLORS["white"], COLORS["line"], 1.8)
    add_shape(s1, 5, 330, 86, 300, 38, COLORS["yellow"], COLORS["yellow"], 0)
    add_text(s1, 351, 92, 258, 24, "学前儿童美术教育", size=18, color=COLORS["white"], bold=True, align=2)
    add_text(s1, 280, 152, 400, 54, "小手变形画", size=32, color=COLORS["text"], bold=True, align=2)
    add_text(s1, 250, 210, 460, 54, "大班绘画活动设计与实施", size=22, color=COLORS["muted"], bold=True, align=2)
    add_shape(s1, 5, 230, 290, 500, 108, COLORS["cream"], COLORS["cream"], 0)
    add_text(s1, 265, 315, 430, 46, "从“小手”出发\n在描画与添画中发展想象力和表现力", size=20, color=COLORS["text"], align=2)
    add_shape(s1, 9, 152, 282, 56, 56, COLORS["pink"], COLORS["pink"], 0)
    add_shape(s1, 9, 746, 282, 56, 56, COLORS["green"], COLORS["green"], 0)

    s2 = slide()
    bg(s2, COLORS["yellow"])
    title_row(s2, "设计意图", "为什么选择“小手变形画”")
    card(s2, 62, 82, 836, 382)
    bullet_block(
        s2, 96, 122, 488, 250,
        [
            "大班幼儿手部控制能力较强，能够相对稳定地描画手形轮廓。",
            "“手”是幼儿最熟悉的对象，容易激发参与兴趣，也能降低绘画活动的进入门槛。",
            "通过变换手势、描画轮廓、借形添画，帮助幼儿完成从具体到想象的思维转换。",
            "活动同时兼顾手眼协调、精细动作、创造联想和表达分享。 "
        ],
        size=21
    )
    card(s2, 620, 118, 232, 278, COLORS["cream"])
    add_text(s2, 668, 148, 136, 28, "活动价值", size=22, bold=True, align=2)
    bullet_block(
        s2, 650, 205, 170, 160,
        ["材料熟悉", "操作简单", "想象空间大", "便于展示交流"],
        size=18
    )

    s3 = slide()
    bg(s3, COLORS["blue"])
    title_row(s3, "活动目标", "目标设置")
    goals = [
        (74, COLORS["cream"], "认知目标", "了解不同手势会形成不同轮廓，理解手形添画的基本方法。"),
        (360, COLORS["pink"], "能力目标", "能摆出并描画至少两种不同手形，并在轮廓基础上添画成完整形象。"),
        (646, COLORS["green"], "情感目标", "积极参与创意活动，敢于想象，乐于展示自己的“手形魔术”作品。"),
    ]
    for left, fill, name, body in goals:
        card(s3, left, 108, 240, 284, fill)
        add_shape(s3, 5, left + 54, 92, 132, 34, COLORS["white"], COLORS["white"], 0)
        add_text(s3, left + 67, 98, 106, 18, name, size=16, bold=True, align=2)
        add_text(s3, left + 28, 158, 184, 152, body, size=20, align=2)
    add_text(s3, 180, 438, 600, 24, "三个目标层次清晰，便于课堂推进和活动评价。", size=18, color=COLORS["muted"], align=2)

    s4 = slide()
    bg(s4, COLORS["cream"])
    title_row(s4, "活动准备", "经验准备与物质准备")
    card(s4, 72, 90, 376, 344)
    card(s4, 512, 90, 376, 344)
    add_shape(s4, 5, 102, 112, 116, 32, COLORS["accent_green"], COLORS["accent_green"], 0)
    add_shape(s4, 5, 542, 112, 116, 32, COLORS["orange"], COLORS["orange"], 0)
    add_text(s4, 116, 118, 88, 18, "经验准备", size=16, color=COLORS["white"], bold=True, align=2)
    add_text(s4, 556, 118, 88, 18, "物质准备", size=16, color=COLORS["white"], bold=True, align=2)
    bullet_block(
        s4, 104, 168, 300, 182,
        ["有描画简单轮廓的经验。", "有过想象创造的经历。", "认识常见动物和植物的外形特征。"],
        size=21
    )
    bullet_block(
        s4, 544, 168, 306, 220,
        ["手形添画范画若干。", "投影仪或示范白纸。", "A3白纸、黑色记号笔、油画棒。", "必要时准备湿巾或围裙，保证活动整洁。"],
        size=20
    )

    s5 = slide()
    bg(s5, COLORS["yellow"])
    title_row(s5, "活动流程", "四个基本环节")
    steps = [
        ("01", "游戏导入", "感知手形变化"),
        ("02", "观察发现", "探索添画方法"),
        ("03", "幼儿创作", "完成手形作品"),
        ("04", "展示交流", "分享创作思路"),
    ]
    fills = [COLORS["pink"], COLORS["light_blue"], COLORS["green"], COLORS["cream"]]
    for i, (num, name, note) in enumerate(steps):
        left = 80 + i * 204
        card(s5, left, 155, 156, 182, fills[i])
        add_shape(s5, 5, left + 45, 132, 66, 36, COLORS["white"], COLORS["white"], 0)
        add_text(s5, left + 53, 139, 50, 20, num, size=20, color=COLORS["orange"], bold=True, align=2)
        add_text(s5, left + 20, 210, 116, 26, name, size=23, bold=True, align=2)
        add_text(s5, left + 18, 260, 120, 48, note, size=17, color=COLORS["muted"], align=2)
    add_text(s5, 220, 404, 520, 24, "时间建议：3分钟 + 8分钟 + 15-18分钟 + 5分钟", size=18, bold=True, align=2)

    s6 = slide()
    bg(s6, COLORS["blue"])
    title_row(s6, "实施重点", "导入与观察示范")
    card(s6, 68, 96, 380, 330)
    card(s6, 512, 96, 380, 330)
    add_shape(s6, 5, 96, 116, 108, 30, COLORS["accent_pink"], COLORS["accent_pink"], 0)
    add_shape(s6, 5, 540, 116, 108, 30, COLORS["accent_blue"], COLORS["accent_blue"], 0)
    add_text(s6, 112, 121, 76, 18, "游戏导入", size=16, color=COLORS["white"], bold=True, align=2)
    add_text(s6, 556, 121, 76, 18, "观察示范", size=16, color=COLORS["white"], bold=True, align=2)
    bullet_block(
        s6, 98, 168, 316, 184,
        ["从“石头、剪刀、布”开始，引导幼儿说出像什么。", "追问“小手还能摆出什么形状”，鼓励自由尝试。", "让幼儿先动手、先表达，再进入正式绘画。"],
        size=21
    )
    bullet_block(
        s6, 542, 168, 316, 200,
        ["教师现场沿手形描边，示范“掌心贴纸、笔沿边走”。", "描完后带领幼儿从不同角度观察轮廓。", "再用简单几笔把轮廓变成具体形象，让方法清楚可学。"],
        size=20
    )

    s7 = slide()
    bg(s7, COLORS["cream"])
    title_row(s7, "实施重点", "幼儿创作与分层指导")
    card(s7, 66, 94, 828, 344)
    add_shape(s7, 5, 94, 116, 126, 32, COLORS["orange"], COLORS["orange"], 0)
    add_shape(s7, 5, 482, 116, 126, 32, COLORS["accent_green"], COLORS["accent_green"], 0)
    add_text(s7, 108, 121, 98, 18, "创作要求", size=16, color=COLORS["white"], bold=True, align=2)
    add_text(s7, 496, 121, 98, 18, "教师指导", size=16, color=COLORS["white"], bold=True, align=2)
    bullet_block(
        s7, 98, 170, 300, 188,
        ["至少摆出两种不同手势。", "先描轮廓，再添画细节，最后涂色。", "既可以一个手形变一个形象，也可以两个手形组合创作。"],
        size=21
    )
    bullet_block(
        s7, 488, 170, 322, 198,
        ["能力较强的幼儿：鼓励转动画纸，多角度联想，并补充场景。", "能力一般的幼儿：提供手势示范，用提问提示添画方向。", "动手吃力的幼儿：帮助固定画纸和手形，降低操作难度。"],
        size=19
    )
    add_shape(s7, 5, 102, 364, 694, 44, COLORS["light_blue"], COLORS["light_blue"], 0)
    add_text(s7, 118, 374, 662, 20, "常规提醒：按住画纸的手不要移动；画完轮廓再上色；注意画面整洁。", size=17, align=2)

    s8 = slide()
    bg(s8, COLORS["yellow"])
    title_row(s8, "展示评价", "作品展示、延伸与反思")
    card(s8, 70, 92, 390, 344)
    card(s8, 500, 92, 390, 344)
    add_shape(s8, 5, 98, 114, 124, 32, COLORS["accent_pink"], COLORS["accent_pink"], 0)
    add_shape(s8, 5, 528, 114, 124, 32, COLORS["accent_blue"], COLORS["accent_blue"], 0)
    add_text(s8, 112, 120, 96, 18, "展示延伸", size=16, color=COLORS["white"], bold=True, align=2)
    add_text(s8, 544, 120, 92, 18, "设计反思", size=16, color=COLORS["white"], bold=True, align=2)
    bullet_block(
        s8, 102, 168, 314, 200,
        ["作品贴在“小手魔术墙”上集中展示。", "引导幼儿用“我摆了……变成了……”介绍思路。", "活动后可继续尝试“手形印画+添画”或“脚印变形画”。"],
        size=20
    )
    bullet_block(
        s8, 532, 168, 316, 214,
        ["大纸作画能降低描边难度，比较适合大班幼儿。", "范画不宜一次性全部铺开，应采用“先猜再揭示”的方式。", "分享环节要关注“创作过程表达”，而不只停留在“画了什么”。"],
        size=19
    )

    s9 = slide()
    bg(s9, COLORS["blue"])
    add_shape(s9, 5, 150, 88, 660, 56, COLORS["yellow"], COLORS["yellow"], 0)
    add_text(s9, 210, 100, 392, 28, "活动预设效果方向", size=28, color=COLORS["white"], bold=True, align=2)
    card(s9, 104, 180, 752, 248)
    add_text(s9, 146, 220, 660, 34, "预设作品可以围绕这些常见联想展开：", size=22, bold=True, align=2)
    add_shape(s9, 5, 160, 288, 120, 44, COLORS["cream"], COLORS["cream"], 0)
    add_shape(s9, 5, 256, 288, 120, 44, COLORS["pink"], COLORS["pink"], 0)
    add_shape(s9, 5, 448, 288, 120, 44, COLORS["green"], COLORS["green"], 0)
    add_shape(s9, 5, 640, 288, 120, 44, COLORS["light_blue"], COLORS["light_blue"], 0)
    add_text(s9, 188, 299, 64, 18, "公鸡", size=18, bold=True, align=2)
    add_text(s9, 284, 299, 64, 18, "章鱼", size=18, bold=True, align=2)
    add_text(s9, 476, 299, 64, 18, "大树", size=18, bold=True, align=2)
    add_text(s9, 668, 299, 64, 18, "蝴蝶", size=18, bold=True, align=2)
    add_text(s9, 178, 356, 620, 22, "重点不是画得一模一样，而是让幼儿在手形基础上大胆联想、完整添画。", size=18, color=COLORS["muted"], align=2)

    if PPT_PATH.exists():
        try:
            PPT_PATH.unlink()
        except PermissionError:
            pass
    presentation.SaveAs(str(PPT_PATH))
    presentation.Close()
    app.Quit()
    print(PPT_PATH)


if __name__ == "__main__":
    build()
