import svgwrite
import xml.etree.ElementTree as ET

from odf.opendocument import load
from odf.table import Table, TableRow, TableColumn, TableCell
from odf.text import P
from odf.style import Style

class Scheduler():
    def schedule(self, infile, outfile):
        self.svg = svgwrite.Drawing(
            outfile,
            debug=False,
            id='root',
        )
        self.padding = 1
        self.margin = 5
        doc = load(infile)
        styles = {}
        for style in doc.getElementsByType(Style):
            name = style.getAttribute('name')
            if not style.firstChild:
                continue
            styles[name] = {key[1]: value for key, value in style.firstChild.attributes.items()}

        table = doc.getElementsByType(Table)[0]
        column_widths = []
        for col in table.getElementsByType(TableColumn):
            style_name = col.getAttribute('stylename')
            repeat = col.getAttribute('numbercolumnsrepeated')
            repeat = int(repeat) if repeat else 1
            for i in range(0, repeat):
                if not style_name or 'column-width' not in styles[style_name]:
                    column_widths.append(50)
                else:
                    column_widths.append(self.convert_to_si(styles[style_name]['column-width']))

        y = self.margin
        for tri, tr in enumerate(table.getElementsByType(TableRow)):
            x = self.margin
            height = 6
            tdi = 0
            for td in tr.getElementsByType(TableCell):
                repeat = td.getAttribute('numbercolumnsrepeated')
                repeat = int(repeat) if repeat else 1
                for i in range(0, repeat):
                    width = column_widths[tdi]
                    self.svg.add(self.svg.rect(insert=(x, y), size=(width, height), style='fill:rgba(255,255,255,1); stroke-width:.125; stroke:rgb(0,0,0)'))
                    value = td.getElementsByType(P)
                    if value:
                        self.add_text(value[0], x+self.padding, y+self.padding)
                    x += width
                    tdi += 1
            y += height
        total_width = sum(column_widths) + (self.margin * 2)
        self.svg['width'] = '{}mm'.format(total_width)
        self.svg['height'] = '{}mm'.format(y)
        self.svg['viewBox'] = '0 0 {} {}'.format(total_width, y)
        self.svg.save(pretty=True)

    def add_text(self, text, x, y):
        self.svg.add(self.svg.text(str(text).upper(), insert=tuple((x, y)), **{
            'font-size': 4.13,
            'font-family': 'OpenGost Type B TT',
            'text-anchor': 'start',
            'alignment-baseline': 'baseline',
            'dominant-baseline': 'hanging'
        }))

    def convert_to_si(self, value):
        if 'in' in value:
            return float(value[0:-2]) * 25.4
