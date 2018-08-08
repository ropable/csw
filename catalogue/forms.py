from django import forms
from django.utils.safestring import mark_safe
from django.contrib.admin.widgets import AdminFileWidget

from catalogue.models import Record, Style, Application


class StyleFileWidget(AdminFileWidget):
    template_name = 'catalogue/widgets/style_file_input.html'

    def get_context(self, name, value, attrs):
        context = super(AdminFileWidget, self).get_context(name, value, attrs)
        context['widget']['readonly'] = getattr(self, "readonly") if hasattr(self, "readonly") else False
        return context


class Select(forms.Select):
    def __init__(self, attrs=None, choices=()):
        super(Select, self).__init__(attrs)

    def render(self, name, value, attrs=None):
        if self.attrs.get('readonly', False):
            self.attrs["disabled"] = True
            del self.attrs['readonly']
            return mark_safe('\n'.join(["<input type='hidden' name='{}' value='{}'>".format(
                name, value or ''), super(Select, self).render(name, value, attrs)]))
        else:
            if 'readonly' in self.attrs:
                del self.attrs['readonly']
            if 'disabled' in self.attrs:
                del self.attrs['disabled']
            return super(Select, self).render(name, value, attrs)


class RecordForm(forms.ModelForm):
    """
    A form for Record Model
    """

    def __init__(self, *args, **kwargs):
        super(RecordForm, self).__init__(*args, **kwargs)
        self.fields['identifier'].widget.attrs['readonly'] = True
        self.fields['legend'].widget.is_required = False

    class Meta:
        model = Record
        fields = ("identifier", "title", "abstract", "keywords", "legend", "any_text", "tags")
        widgets = {
            'keywords': forms.TextInput(attrs={"style": "width:70%"})
        }


class StyleForm(forms.ModelForm):
    """
    A form for Style Model
    """

    def __init__(self, *args, **kwargs):
        super(StyleForm, self).__init__(*args, **kwargs)
        if 'instance' in kwargs and kwargs['instance'] and kwargs['instance'].pk:
            self.fields['name'].widget.attrs['readonly'] = True
            if kwargs['instance'].name == Style.BUILTIN:
                self.fields['content'].widget.readonly = True
            else:
                self.fields['content'].widget.readonly = False
            self.fields['content'].widget.is_required = True
            self.fields['record'].widget = self.fields['record'].widget.widget
            self.fields['record'].widget.attrs['readonly'] = True
            self.fields['format'].widget.attrs['readonly'] = True

    class Meta:
        model = Style
        fields = ("name", "record", "format", "content", "default")
        widgets = {
            'record': Select(),
            'format': Select(),
            'content': StyleFileWidget()
        }


class ApplicationForm(forms.ModelForm):
    """
    A form for Application Model
    """

    def __init__(self, *args, **kwargs):
        super(ApplicationForm, self).__init__(*args, **kwargs)
        if 'instance' in kwargs and kwargs['instance'] and kwargs['instance'].pk:
            self.fields['name'].widget.attrs['readonly'] = True

    class Meta:
        model = Application
        fields = "__all__"
