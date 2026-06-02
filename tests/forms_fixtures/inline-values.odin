{$}
odin = "1.0.0"
forms = "1.0.0"
title = "Inline Values"
id = "inline_form"
lang = "en"

{$.page}
width = #8.5
height = #11
unit = "inch"

{page[0]}
{.field.name}
type = "text"
x = #0.6
y = #1.55
w = #3.5
h = #0.3
label = "Full Name"
value = "John Smith"
inputType = "email"
bind = @insured.name

{.field.agree}
type = "checkbox"
x = #0.5
y = #8
w = #0.2
h = #0.2
label = "I agree"
checked = ?true
bind = @application.termsAccepted

{.field.dob}
type = "date"
x = #4
y = #2.25
w = #1.5
h = #0.25
label = "Date of Birth"
value = 1985-03-15
min = 1900-01-01
max = 2010-01-01
bind = @insured.birthDate

{.field.state}
type = "select"
x = #4
y = #3
w = #1.5
h = #0.3
label = "State"
selected = "TX"
bind = @insured.address.state

{.field.state.options[] : ~}
"AL"
"CA"
"NY"
"TX"
