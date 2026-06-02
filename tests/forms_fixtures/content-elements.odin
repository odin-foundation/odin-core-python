{$}
odin = "1.0.0"
forms = "1.0.0"
title = "Content Elements"
id = "content_form"
lang = "en"

{$.i18n}
en.field_name = "Full Legal Name"

{$.page}
width = #8.5
height = #11
unit = "inch"
margin.top = #0.5
margin.right = #0.25
margin.bottom = #0.6
margin.left = #0.75

{page[0]}
{.img.template}
x = #0
y = #0
w = #8.5
h = #11
src = ^png:iVBORw0KGgo=
alt = "Page template"
background = ?true

{.barcode.doc}
x = #7
y = #0.5
w = #1
h = #1
type = "qr"
content = "DOC-2024-001234"
alt = "Document tracking code"

{.field.name}
type = "text"
x = #0.6
y = #1.55
w = #3.5
h = #0.3
label = @$.i18n.en.field_name
bind = @insured.name
