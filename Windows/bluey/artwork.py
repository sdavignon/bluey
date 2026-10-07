"""Render the original iOS BlobShape/FaceView geometry for Windows assets.

Run `python -m bluey.artwork` before packaging. No external image service.
"""
from pathlib import Path
import math
from PIL import Image, ImageChops, ImageDraw


def character():
    image = Image.new("RGBA", (844, 760))
    mask = Image.new("L", image.size)
    points = [(438.4, 44)]
    k = .5523
    curves = [((832-393.6*(1-k),44),(832,44+392*(1-k)),(832,436)),
              ((832,744-308*(1-k)),(832-377.2*(1-k),744),(454.8,744)),
              ((12+442.8*(1-k),744),(12,744-294*(1-k)),(12,450)),
              ((12,44+406*(1-k)),(12+426.4*(1-k),44),(438.4,44))]
    for a,b,c in curves:
        start = points[-1]
        for step in range(1,81):
            t=step/80; u=1-t
            points.append(tuple(u**3*start[i]+3*u*u*t*a[i]+3*u*t*t*b[i]+t**3*c[i] for i in (0,1)))
    ImageDraw.Draw(mask).polygon(points, fill=255)
    colors = [(169,188,255),(108,134,245),(66,84,214),(43,47,143)]
    stops = [0,.34,.68,1]
    pixels=[]
    for y in range(760):
        for x in range(844):
            t=max(0,min(1,((x-217)*410+(y-90.9)*606.2)/(410**2+606.2**2)))
            i=next((n for n in range(3) if t<=stops[n+1]),2)
            f=(t-stops[i])/(stops[i+1]-stops[i])
            shine=.5*max(0,1-math.hypot(x-258,y-170)/243)
            rgb=[round((colors[i][c]*(1-f)+colors[i+1][c]*f)*(1-shine)+255*shine) for c in range(3)]
            pixels.append(tuple(rgb)+(255,))
    image.putdata(pixels); image.putalpha(mask)
    highlight=Image.new("RGBA", image.size)
    ImageDraw.Draw(highlight).ellipse((202,84,248,106),fill=(255,255,255,90))
    highlight.putalpha(ImageChops.multiply(highlight.getchannel("A"),mask))
    image.alpha_composite(highlight)
    draw=ImageDraw.Draw(image)
    navy="#1c1f66"; ink="#17151f"
    crown=[(30,4),(36,16),(52,12),(40,24),(46,36),(30,28),(14,36),(20,24),(8,12),(24,16)]
    draw.polygon([(380+x*1.4,21+y*1.4) for x,y in crown], fill=navy)
    for side in (-1,1):
        ex=422+side*130; ey=201
        # Quadratic brows from FaceView, sampled into a smooth stroke.
        brow=[]
        for n in range(41):
            t=n/40; u=1-t
            brow.append((ex+side*6-38*u*u+38*t*t,ey-119+6*u*u-24*u*t+6*t*t))
        draw.line(brow,fill=navy,width=14,joint="curve")
        draw.ellipse((ex-95,ey-95,ex+95,ey+95),fill="white")
        px=ex-side*3; py=ey-12; r=46*1.12
        draw.ellipse((px-r,py-r,px+r,py+r),fill=ink)
        for dx,dy,rr in [(-.30,-.44,.28),(.40,.34,.12)]:
            cx=px+r*dx; cy=py+r*dy; cr=r*rr
            draw.ellipse((cx-cr,cy-cr,cx+cr,cy+cr),fill="white")
    draw.ellipse((392,316,452,354),fill=navy)
    return image


def build():
    target=Path(__file__).parent / "assets"
    target.mkdir(exist_ok=True)
    art=character()
    art.save(target / "bluey.png")
    # Square phone-style crop keeps the expressive face readable at taskbar size.
    icon=Image.new("RGBA",(844,844),(13,14,24,255))
    face=art.crop((92,0,752,660)).resize((844,844),Image.Resampling.LANCZOS)
    icon.alpha_composite(face)
    icon.resize((256,256),Image.Resampling.LANCZOS).save(target / "bluey.ico",sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])


if __name__ == "__main__":
    build()
