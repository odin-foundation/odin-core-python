{$}
odin = "1.0.0"
forms = "1.0.0"
title = "Template Form"
id = "tpl_form"
lang = "en"

{$.page}
width = #8.5
height = #11
unit = "inch"

{page[0]}
{.text.header}
x = #0.5
y = #0.5
content = "Vehicles — Page {@odin.page} of {@odin.total_pages}"
font-size = ##14
font-weight = "bold"

{.region.vehicles}
x = #0.5
y = #1.2
w = #7.5
h = #6
bind = @policy.vehicles
max = ##3
overflow = @tpl_vehicles_continued

{.region.vehicles.field.vin}
x = #0
y = #0.15
y-offset = #1.8
w = #4
h = #0.3
label = "VIN"
bind = @.vin

{@tpl_vehicles_continued}
page-template = ?true
continues = "region.vehicles"
form-id = "PA (Cont)"

{.text.header}
x = #0.5
y = #0.5
content = "Additional Vehicles — Page {@odin.page} of {@odin.total_pages}"
font-size = ##14
font-weight = "bold"

{.region.vehicles}
x = #0.5
y = #1
w = #7.5
h = #8
max = ##4
overflow = @tpl_vehicles_continued

{.region.vehicles.field.vin}
x = #0
y = #0.15
y-offset = #1.2
w = #4
h = #0.3
label = "VIN"
bind = @.vin
