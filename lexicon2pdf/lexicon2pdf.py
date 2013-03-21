#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 coding=utf-8
# maintainer: rgaudin

import sys
import os
import locale
from operator import attrgetter
from xml.dom import minidom
from xml.dom.minidom import Node

import reportlab.platypus as platypus
import reportlab.rl_config
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import *
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
# registerFontFamily not available on Ubuntu LTS 8.04
#from reportlab.pdfbase.pdfmetrics import registerFontFamily


class CodesHolder(object):

    def __init__(self):
        self.objects = {}

    def get(self, code):
        return self.get_obj(code)

    def get_abbr(self, code):
        try:
            return self.codes[code].abbr
        except:
            return None

    def get_obj(self, code):
        try:
            return self.objects[code]
        except:
            return None

    def get_name(self, code):
        try:
            return self.objects[code]['name']
        except:
            return None

    def add(self, code, abbr, name):
        self.objects[code] = Nature(code=code, abbr=abbr, name=name)


class Nature(object):
    code = None
    abbr = None
    name = None

    def __init__(self, code, abbr=None, name=None):
        self.code = code
        if abbr:
            self.abbr = abbr
        if name:
            self.name = name

    def display_name(self):
        return self.abbr

    def __str__(self):
        return self.display_name()


class Word(object):

    name = None
    derivatives = []

    def __init__(self, name=None):
        if name:
            self.name = name
        self.derivatives = []

    def add_deriv(self, deriv):
        self.derivatives.append(deriv)

    def display_name(self):
        return self.name

    def __str__(self):
        return self.display_name()


class Translation(object):
    nature = None
    name = None

    def __init__(self, name=None, nature=None):
        if name:
            self.name = name
        if nature:
            self.nature = nature

    def display_name(self):
        str_ = u"%(name)s" % {'name': self.name}
        if self.nature:
            str_ += u" (%(nat)s)" % {'nat': self.nature.display_name()}
        return str_

    def __str__(self):
        return self.display_name()


class Derivative(object):

    nature = None
    name = None
    translations = []

    def __init__(self, name=None, nature=None):
        if name:
            self.name = name
        if nature:
            self.nature = nature
        self.translations = []

    def add_trans(self, trans):
        self.translations.append(trans)

    def display_name(self):
        str_ = u"%(name)s" % {'name': self.name}
        if self.nature:
            str_ += u" (%(nat)s)" % {'nat': self.nature.display_name()}
        return str_

    def __str__(self):
        return self.display_name()


class Dictionary(object):

    source = None
    target = None
    source_name = None
    target_name = None
    words = []

    def __init__(self, source, target, source_name=None, target_name=None):
        self.source = source
        self.target = target
        if source_name:
            self.source_name = source_name
        if target_name:
            self.target_name = target_name
        self.words = []

    def display_source(self):
        if self.source_name:
            return self.source_name.title()
        else:
            return self.source.upper()

    def display_target(self):
        if self.target_name:
            return self.target_name.title()
        else:
            return self.target.upper()

    def display_name(self):
        return u"%(source)s-%(target)s" % {'source': self.display_source(),
                                           'target': self.display_target()}


class PDFDictionary(object):

    title = None
    total_pages = 0

    def __init__(self, file_name, dico, title=None):
        self.file_name = file_name
        self.dico = dico
        if title:
            self.title = title

        self.elements = []
        self.styles = {}
        self.unit = 1
        self.init_layout()

    def get_title(self):
        if self.title:
            return self.title
        else:
            return self.dico.display_name()

    def get_sub_title(self):
        if self.sub_title:
            return self.sub_title

    def build_elements(self):
        ''' generate reportlab Paragraph from data

        Create only one paragraph per word (prevent definition splitted
        across pages.
        Display as follow:
            word (nat.) : translation
        if there is no derivative or:
            word
            nat. derivative : translation
        for multiple ones. '''

        for word in self.dico.words:
            single = False
            para = u""
            if word.derivatives.__len__() == 1:
                single = True
            else:
                word_name = u"<font name='DejaVuSansMono-Bold'>%s</font>" % word.display_name()
                para += word_name

            for derivative in word.derivatives:

                # derivative name + nature
                deriv = u""
                if single:
                    deriv += u"%(deriv)s" % \
                             {'deriv': u"<font name='DejaVuSansMono-Bold'>%s</font>" % word.display_name()}
                    if derivative.nature:
                        deriv += u" (<font name='DejaVuSansMono-Oblique'>%(nat)s</font>)" \
                                 % {'nat': derivative.nature}
                else:
                    if derivative.nature:
                        deriv += u"<font name='DejaVuSansMono-Oblique'>%(nat)s</font> " \
                                 % {'nat': derivative.nature}
                    deriv += derivative.name

                # init trad text
                trads = u""
                for translation in derivative.translations:
                    if (trads.__len__() > 0):
                        trads += u", "
                    trads += u"%(trad)s" % {'trad': translation.display_name()}

                if not single: #para.__len__() > 0:
                    para += u"<br />"
                para += "%(deriv)s : %(trads)s" \
                        % {'deriv': deriv, 'trads': trads}
            self.elements.append(\
                              Paragraph(para, self.styles['translation_line']))

    def init_layout(self):

        self.unit = reportlab.lib.units.inch

        self.init_fonts()
        self.init_styles()

        self.document = platypus.BaseDocTemplate(self.file_name, \
                        pagesize=reportlab.lib.pagesizes.A4, leftMargin=20, \
                        rightMargin=20, topMargin=40, bottomMargin=10, \
                        allowSplitting=0, title=self.get_title(), \
                        author="Kunnafoni")
        frameCount = 2
        frameWidth = self.document.width / frameCount
        frameHeight = self.document.height - .05 * self.unit
        frames = []
        #construct a frame for each column
        for frame in range(frameCount):

            leftMargin = self.document.leftMargin + frame * frameWidth
            column = platypus.Frame(leftMargin, self.document.bottomMargin, \
                                    frameWidth, frameHeight)
            frames.append(column)

        template = platypus.PageTemplate(frames=frames, onPage=self.addHeader)
        self.document.addPageTemplates(template)

    def init_fonts(self):
        # disable warning on missing glyphs
        reportlab.rl_config.warnOnMissingFontGlyphs = 0

        pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))
        pdfmetrics.registerFont(TTFont('DejaVuSansMono', 'DejaVuSansMono.ttf'))
        pdfmetrics.registerFont(TTFont('DejaVuSansMono-Bold', \
                                       'DejaVuSansMono-Bold.ttf'))
        pdfmetrics.registerFont(TTFont('DejaVuSansMono-Oblique', \
                                       'DejaVuSansMono-Oblique.ttf'))
        pdfmetrics.registerFont(TTFont('DejaVuSansMono-BoldOblique', \
                                       'DejaVuSansMono-BoldOblique.ttf'))
        '''
        registerFontFamily is not available on Ubuntu LTS 8.04
        registerFontFamily('DejaVuSansMono', normal='DejaVuSansMono', \
                           bold='DejaVuSansMono-Bold', \
                           italic='DejaVuSansMono-Oblique', \
                           boldItalic='DejaVuSansMono-BoldOblique')'''

    def init_styles(self):
        styles = getSampleStyleSheet()

        self.styles['translation_line'] = styles['Normal']
        self.styles['translation_line'].fontName = 'DejaVuSansMono'
        self.styles['translation_line'].fontSize = 8
        self.styles['translation_line'].spaceAfter = self.unit * .04
        self.styles['translation_line'].leading = 9
        self.styles['translation_line'].spaceBefore = 0
        self.styles['translation_line'].spaceAfter = 0

    def addHeader(self, canvas, document):

        # update total_pages counter
        if document.page > self.total_pages:
            self.total_pages = document.page

        canvas.saveState()
        title = u"%s (%s)" % (self.get_title(), self.dico.words.__len__())
        fontsize = 11
        fontname = 'DejaVuSans'
        headerBottom = document.bottomMargin + document.height \
                       + document.topMargin / 3
        bottomLine = headerBottom - fontsize / 4
        topLine = headerBottom + fontsize
        lineLength = document.width + document.leftMargin
        canvas.setFont(fontname, fontsize)
        pages = u"%s/%s" % (str(document.page), str(self.total_pages))
        if document.page % 2:
            #odd page: put the page number on the right and align right
            title = title + " " + pages
            canvas.drawRightString(lineLength, headerBottom, title)
        else:
            #even page: put the page number on the left and align left
            title = pages + " " + title
            canvas.drawString(document.leftMargin, headerBottom, title)
        #draw some lines to make it look cool
        canvas.setLineWidth(1)
        canvas.line(document.leftMargin, bottomLine, lineLength, bottomLine)
        canvas.line(document.leftMargin, topLine, lineLength, topLine)
        canvas.restoreState()

    def run(self):
        self.build_elements()
        self.save()

    def run_twice(self):
        self.run()
        self.elements = []
        self.run()

    def save(self):
        self.document.build(self.elements)


def parse_xml_dict(dict_file):

    xmldoc = minidom.parse(dict_file)

    codes = CodesHolder()

    # getting dictionary infos
    src = xmldoc.childNodes[0].getAttribute('source')
    tgt = xmldoc.childNodes[0].getAttribute('target')
    src_name = xmldoc.childNodes[0].getAttribute('source_name')
    tgt_name = xmldoc.childNodes[0].getAttribute('target_name')

    dico = Dictionary(source=src, target=tgt, \
                      source_name=src_name, target_name=tgt_name)

    # Parsing XML codes
    for node in xmldoc.getElementsByTagName("code"):
        code = node.getAttribute('value')
        abbr = node.getAttribute('abbr')
        name = node.childNodes[0].data
        codes.add(code=code, abbr=abbr, name=name)

    # Parsing XML words
    for node in xmldoc.getElementsByTagName("word"):
        word = node.getElementsByTagName("value")[0].childNodes[0].data

        # word is content of <value> child
        word = node.getElementsByTagName("value")[0].childNodes[0].data
        wob = Word(word)

        # derivatives are stored in <derivative> nodes
        derivatives = node.getElementsByTagName("derivative")

        for derivative in derivatives:
            try:
                derivative_name = derivative\
                           .getElementsByTagName("value")[0].childNodes[0].data
            except IndexError:
                derivative_name = word
            derivative_type = codes.get(derivative.getAttribute('type'))
            dob = Derivative(name=derivative_name, nature=derivative_type)
            found = False

            for translation in derivative.getElementsByTagName('translation'):
                translation_name = translation.childNodes[0].data
                translation_type = codes.get(translation.getAttribute('type'))
                tob = Translation(name=translation_name, \
                                  nature=translation_type)

                # add translation to derivative (only if not present)
                for extob in dob.translations:
                    if extob.name == tob.name and extob.nature == tob.nature:
                        found = True
                if not found:
                    dob.add_trans(tob)

            # add derivative to word
            wob.add_deriv(dob)

        # add word to mapping
        dico.words.append(wob)

    return dico


def usage():
    print "wiki_lexicon: Generates a PDF lexicon from an XML source file.\n" \
          "Usage: %s source_file [dest_file]" % sys.argv[0]


def dest_file_from_source(source):
    head, sep, tail = source.rpartition('.')
    if sep:
        dest = head + sep + 'pdf'
    else:
        dest = tail + '.pdf'
    return dest


def main():

    # initialize locale for later sorting
    locale.setlocale(locale.LC_ALL, "")

    # command line arguments
    if sys.argv.__len__() < 2:
        usage()
        exit(0)

    # XML source file is mandatory
    source_file = sys.argv[1]
    if not os.path.exists(source_file):
        print "Unable to find XML source file %s." % source_file
        exit(1)

    # if no destination file provided
    # use same name with pdf extension
    if sys.argv.__len__() >= 3:
        dest_file = sys.argv[2]
    else:
        dest_file = dest_file_from_source(source_file)

    # parsing XML into our dictionary model
    dico = parse_xml_dict(source_file)

    # sorting lexicon alphabeticaly
    dico.words.sort(key=attrgetter('name'), cmp=locale.strcoll)

    # build PDF
    # we run twice to be able to use total number of pages
    pdf_title = u"Lexicon %s -- Wiktionary" % dico.display_name()
    pdf = PDFDictionary(dest_file, dico, title=pdf_title)
    pdf.run_twice()


if __name__ == '__main__':
    main()
