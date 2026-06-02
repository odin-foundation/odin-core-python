{$}
odin = "1.0.0"
forms = "1.0.0"
title = "Signature and Radio"
id = "sigradio_form"
lang = "en"

{$.page}
width = #8.5
height = #11
unit = "inch"

{page[0]}
{.field.gender_m}
type = "radio"
x = #0.6
y = #2
w = #0.2
h = #0.2
label = "Male"
group = "gender"
value = "M"
bind = @applicant.gender

{.field.gender_f}
type = "radio"
x = #1.6
y = #2
w = #0.2
h = #0.2
label = "Female"
group = "gender"
value = "F"
bind = @applicant.gender

{.field.gender_x}
type = "radio"
x = #2.6
y = #2
w = #0.2
h = #0.2
label = "Nonbinary"
group = "gender"
value = "X"
bind = @applicant.gender

{.field.applicant_sig}
type = "signature"
x = #0.6
y = #8
w = #3
h = #0.6
label = "Applicant Signature"
required = ?true
value = ^png:iVBORw0KGgo=
date_field = @page[0].field.sig_date
bind = @applicant.signature

{.field.sig_date}
type = "date"
x = #4
y = #8
w = #1.5
h = #0.3
label = "Date Signed"
value = 2026-01-15
bind = @applicant.signatureDate
