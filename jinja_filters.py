import jinja2
import re

special_re = re.compile(r'([\[\](){}+.`!\\])')
def markdown_quote(s):
	return ' '.join(special_re.sub(r'\\\1', s).split())
