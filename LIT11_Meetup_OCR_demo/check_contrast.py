"""Check the explicit UI color pairs; this is not a rendered accessibility audit."""
def luminance(hex_color):
    rgb = [int(hex_color[i:i+2],16)/255 for i in (1,3,5)]
    linear = [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in rgb]
    return sum(v*w for v,w in zip(linear,(.2126,.7152,.0722)))

for foreground, background in [
    ("#0F172A","#FFFFFF"), ("#475569","#FFFFFF"), ("#475569","#F1F5F9"),
    ("#FFFFFF","#0F766E"), ("#FFFFFF","#102b41"), ("#daebef","#102b41"),
    ("#98e4d3","#102b41"), ("#1d4ed8","#FFFFFF"), ("#1d4ed8","#F1F5F9"),
]:
    a,b = sorted((luminance(foreground),luminance(background)))
    ratio = (b+.05)/(a+.05)
    print(f"{foreground} on {background}: {ratio:.2f}:1")
    assert ratio >= 4.5
