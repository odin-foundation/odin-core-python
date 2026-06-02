{$}
odin = "1.0.0"
forms = "1.0.0"
title = "Geometric Elements"
id = "geometric_form"
lang = "en"

{$.page}
width = #8.5
height = #11
unit = "inch"

{page[0]}
{.circle.seal}
cx = #2
cy = #2
r = #0.75
stroke = "#003366"
stroke-width = #0.02
fill = "#e6f0ff"

{.ellipse.stamp}
cx = #5
cy = #2
rx = #1
ry = #0.5
stroke = "#660000"
stroke-width = #0.02
fill = "none"

{.polygon.badge}
points = "1,4 2,4 2.5,5 1.5,5.5 0.5,5"
stroke = "#000000"
stroke-width = #0.01
fill = "#fff8e6"

{.polyline.trend}
points = "3,4 3.5,4.6 4,4.2 4.5,5 5,4.3"
stroke = "#006600"
stroke-width = #0.02

{.path.arrow}
d = "M 6,4 L 7,4 L 6.5,5 Z"
stroke = "#333333"
stroke-width = #0.01
fill = "#cccccc"
