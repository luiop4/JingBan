from PIL import Image, ImageDraw, ImageFont
import math

W, H = 400, 400
img = Image.new("RGBA", (W, H), (0,0,0,0))
d = ImageDraw.Draw(img)

# 背景圆
d.ellipse([20,20,380,380], fill=(226,240,255,255), outline=(90,140,200,255), width=6)

# 鲸鱼身体（椭圆）
body = [70,150,330,290]
d.ellipse(body, fill=(120,170,225,255), outline=(60,110,180,255), width=5)

# 尾巴（三角）
d.polygon([(330,220),(375,180),(370,235)], fill=(120,170,225,255), outline=(60,110,180,255))
d.polygon([(330,220),(375,260),(370,205)], fill=(120,170,225,255), outline=(60,110,180,255))

# 肚子（浅色）
d.ellipse([95,215,305,285], fill=(225,240,255,255))

# 眼睛
d.ellipse([130,185,165,220], fill=(255,255,255,255), outline=(50,80,130,255), width=3)
d.ellipse([142,197,158,213], fill=(40,60,100,255))
d.ellipse([146,200,152,206], fill=(255,255,255,255))

d.ellipse([235,185,270,220], fill=(255,255,255,255), outline=(50,80,130,255), width=3)
d.ellipse([247,197,263,213], fill=(40,60,100,255))
d.ellipse([251,200,257,206], fill=(255,255,255,255))

# 腮红
d.ellipse([115,225,145,245], fill=(255,180,190,180))
d.ellipse([255,225,285,245], fill=(255,180,190,180))

# 嘴（小 w）
d.arc([175,235,205,265], 0, 180, fill=(50,80,130,255), width=4)
d.arc([195,235,225,265], 0, 180, fill=(50,80,130,255), width=4)

# 呆毛
d.line([(195,150),(185,110),(205,95)], fill=(60,110,180,255), width=6)

# 喷水
for i in range(3):
    d.ellipse([180+i*18, 100-i*8, 196+i*18, 116-i*8], fill=(150,200,240,255))

# 文字
try:
    f = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 34)
except:
    f = ImageFont.load_default()
text = "本鲸饿了"
bbox = d.textbbox((0,0), text, font=f)
tw = bbox[2]-bbox[0]
d.text(((W-tw)/2, 315), text, font=f, fill=(50,80,130,255))

img.save(r"I:\AIChatMemory\dafeiyu_sticker.png")
print("saved")
