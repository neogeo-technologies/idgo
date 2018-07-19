from django.forms.widgets import SelectMultiple


class MapSelectMultipleWidget(SelectMultiple):
    template_name = 'idgo_admin/widgets/map_select_multiple.html'
