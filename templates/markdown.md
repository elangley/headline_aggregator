# Links

{% for column in columns %}
	{% for title, link, sep, blog_title, img in column %}
{% if blog_title %}## {{title | mesc}} -- <{{link}}>
{% else %}- {{title | mesc}} -- <{{link}}>{%endif%}{% if sep %}


{% endif %}{% endfor %}
{% endfor %}
