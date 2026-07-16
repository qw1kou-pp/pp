import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from win32com.client import DispatchEx


ROOT = Path(r"E:\codex")
SRC_PPT = ROOT / "小手变形画_幼教风格课件_适配版.pptx"
OUT_PPT = ROOT / "小手变形画_幼教风格课件_适配版_改图.pptx"
TMP_SRC = ROOT / "ppt_source_tmp.pptx"
TMP_OUT = ROOT / "ppt_fixed_tmp.pptx"
IMG_PATH = ROOT / "generated_figs" / "hand_examples_better.png"

W, H = 1552, 684


def load_font(size: int, bold: bool = False):
    candidates = [
        r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


FONT_TITLE = load_font(42, bold=True)
FONT_LABEL = load_font(32, bold=True)
FONT_BODY = load_font(26, bold=True)
FONT_FOOT = load_font(28, bold=True)


def rounded_box(draw, xy, fill, outline="#555555", width=4, radius=36):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def label_box(draw, x, y, text):
    rounded_box(draw, (x, y, x + 120, y + 44), fill="white", outline="white", width=1, radius=18)
    draw.text((x + 20, y + 6), text, font=FONT_LABEL, fill="#4d4d4d")


def draw_rooster(draw, x, y):
    skin = "#f6c9c0"
    line = "#ea7a73"
    hand = [
        (x + 24, y + 130), (x + 46, y + 92), (x + 78, y + 42), (x + 116, y + 100),
        (x + 130, y + 24), (x + 162, y + 20), (x + 160, y + 108), (x + 188, y + 8),
        (x + 220, y + 12), (x + 210, y + 110), (x + 236, y + 34), (x + 264, y + 40),
        (x + 242, y + 126), (x + 210, y + 182), (x + 188, y + 248), (x + 116, y + 268),
        (x + 74, y + 260), (x + 48, y + 208), (x + 52, y + 156),
    ]
    draw.polygon(hand, fill=skin, outline=line)
    draw.line((x + 88, y + 186, x + 126, y + 216), fill="#d46e65", width=5)
    draw.ellipse((x + 248, y + 52, x + 344, y + 148), fill="#fff5d8", outline="#474747", width=4)
    draw.ellipse((x + 296, y + 84, x + 312, y + 100), fill="#333333")
    draw.polygon([(x + 342, y + 98), (x + 392, y + 78), (x + 390, y + 124)], fill="#ffac4e", outline="#ce7d28")
    draw.arc((x + 252, y + 8, x + 334, y + 76), start=190, end=355, fill="#f46c67", width=6)
    draw.arc((x + 270, y - 4, x + 352, y + 64), start=190, end=340, fill="#f46c67", width=6)
    draw.line((x + 290, y + 148, x + 282, y + 226), fill="#a85e21", width=5)
    draw.line((x + 328, y + 148, x + 342, y + 226), fill="#a85e21", width=5)


def draw_octopus(draw, x, y):
    draw.ellipse((x + 92, y + 34, x + 294, y + 236), fill="#f186a9", outline="#4b4b4b", width=4)
    draw.ellipse((x + 154, y + 130, x + 182, y + 158), fill="#2f2f38")
    draw.ellipse((x + 206, y + 130, x + 234, y + 158), fill="#2f2f38")
    draw.arc((x + 156, y + 154, x + 236, y + 208), start=12, end=170, fill="#473941", width=5)
    base_x = x + 112
    for i in range(5):
        lx = base_x + i * 42
        points = [(lx, y + 222), (lx - 12, y + 290), (lx + 8, y + 330), (lx - 6, y + 370)]
        draw.line(points, fill="#ff91b5", width=18, joint="curve")
        for py in (y + 270, y + 308, y + 346):
            draw.ellipse((lx - 14, py - 10, lx + 2, py + 6), fill="#ffd9e4")


def draw_tree(draw, x, y):
    draw.rounded_rectangle((x + 150, y + 186, x + 210, y + 270), radius=18, fill="#a96d3f", outline="#6f482a", width=4)
    for cx, cy, r in [(120, 118, 64), (186, 92, 72), (250, 132, 64), (160, 158, 72)]:
        draw.ellipse((x + cx - r, y + cy - r, x + cx + r, y + cy + r), fill="#9be052", outline="#4b6941", width=4)


def draw_butterfly(draw, x, y):
    draw.ellipse((x + 108, y + 96, x + 206, y + 194), fill="#f49ab1", outline="#545454", width=4)
    draw.ellipse((x + 226, y + 96, x + 324, y + 194), fill="#ffd66e", outline="#545454", width=4)
    draw.ellipse((x + 122, y + 190, x + 220, y + 288), fill="#87b9e5", outline="#545454", width=4)
    draw.ellipse((x + 214, y + 190, x + 312, y + 288), fill="#b4e57a", outline="#545454", width=4)
    draw.rounded_rectangle((x + 205, y + 150, x + 238, y + 274), radius=16, fill="#7b46ad")
    draw.line((x + 214, y + 148, x + 190, y + 112), fill="#666666", width=4)
    draw.line((x + 230, y + 148, x + 252, y + 112), fill="#666666", width=4)
    draw.ellipse((x + 182, y + 98, x + 200, y + 116), fill="#f9bf53")
    draw.ellipse((x + 244, y + 98, x + 262, y + 116), fill="#f9bf53")


def create_image():
    img = Image.new("RGB", (W, H), "#fbf1df")
    draw = ImageDraw.Draw(img)

    rounded_box(draw, (24, 18, W - 24, H - 18), fill="#f7f7f7", outline="#444444", width=4, radius=34)
    rounded_box(draw, (552, 26, 998, 92), fill="#ffce48", outline="#ffce48", width=1, radius=22)
    draw.text((628, 36), "小手变形示意", font=FONT_TITLE, fill="white")

    panels = [
        ((58, 128, 704, 314), "#ffecbe", "公鸡", "张开的手形\n添画成大公鸡"),
        ((846, 128, 1492, 314), "#cfe7f8", "章鱼", "手形倒过来看\n可以变成章鱼"),
        ((58, 364, 704, 550), "#dbf2ce", "大树", "五指像树冠\n掌心像树干"),
        ((846, 364, 1492, 550), "#f8dcea", "蝴蝶", "两个手形组合\n还能变成蝴蝶"),
    ]
    for box, fill, title, body in panels:
        rounded_box(draw, box, fill=fill)
        label_box(draw, box[0] + 22, box[1] + 18, title)
        draw.text((box[0] + 34, box[3] - 72), body, font=FONT_BODY, fill="#545454")

    draw_rooster(draw, 250, 146)
    draw_octopus(draw, 1010, 124)
    draw_tree(draw, 226, 384)
    draw_butterfly(draw, 1040, 400)

    draw.text((86, 602), "提示：先摆手势，再描轮廓，最后添画细节和颜色。", font=FONT_FOOT, fill="#595959")

    IMG_PATH.parent.mkdir(parents=True, exist_ok=True)
    img.save(IMG_PATH)


def replace_picture():
    shutil.copyfile(SRC_PPT, TMP_SRC)

    app = DispatchEx("PowerPoint.Application")
    app.Visible = 1
    app.DisplayAlerts = 0

    presentation = app.Presentations.Open(str(TMP_SRC), False, False, False)
    slide = presentation.Slides.Item(11)
    pic = slide.Shapes.Item("Picture 6")
    left, top, width, height = pic.Left, pic.Top, pic.Width, pic.Height
    pic.Delete()
    slide.Shapes.AddPicture(str(IMG_PATH), False, True, left, top, width, height)

    if TMP_OUT.exists():
        try:
            TMP_OUT.unlink()
        except PermissionError:
            pass

    presentation.SaveAs(str(TMP_OUT))
    presentation.Close()
    app.Quit()
    shutil.copyfile(TMP_OUT, OUT_PPT)


if __name__ == "__main__":
    create_image()
    replace_picture()
    print(OUT_PPT)
