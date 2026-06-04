from django import template
register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Access dict value by key in templates: {{ mydict|get_item:key }}"""
    if dictionary is None:
        return []
    return dictionary.get(key, [])
