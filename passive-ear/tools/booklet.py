#!/usr/bin/env python3
"""Build a readable illustrated PDF from the canonical design document."""
from pathlib import Path
import re
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle, Preformatted, KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT
ROOT=Path(__file__).resolve().parents[1]; DOC=ROOT/'docs'; FONT=Path('/usr/share/fonts/truetype/dejavu')
if (FONT/'DejaVuSans.ttf').exists():
    pdfmetrics.registerFont(TTFont('Body',str(FONT/'DejaVuSans.ttf')))
    pdfmetrics.registerFont(TTFont('BodyBold',str(FONT/'DejaVuSans-Bold.ttf')))
    pdfmetrics.registerFontFamily('Body',normal='Body',bold='BodyBold',italic='Body',boldItalic='BodyBold')
    regular,bold='Body','BodyBold'
else: regular,bold='Helvetica','Helvetica-Bold'
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='Text',fontName=regular,fontSize=9,leading=14,spaceAfter=8,textColor=colors.HexColor('#173b33')))
styles.add(ParagraphStyle(name='SmallText',parent=styles['Text'],fontSize=7.5,leading=11))
for key,size in [('Heading1',20),('Heading2',15),('Heading3',11)]:
    styles[key].fontName=bold;styles[key].fontSize=size;styles[key].leading=size+5;styles[key].textColor=colors.HexColor('#173b33');styles[key].spaceBefore=15;styles[key].spaceAfter=9

def fmt(s):
    s=escape(s)
    s=re.sub(r'\*\*(.*?)\*\*',r'<b>\1</b>',s)
    s=re.sub(r'`([^`]+)`',r'<font color="#52685b">\1</font>',s)
    return s
story=[]
story.append(Paragraph('PEBBLE / P0',styles['Heading1']))
story.append(Paragraph('A passive earbud research concept',styles['Heading1']))
story.append(Paragraph('Independent engineering dossier · 18 October 2026',styles['Text']))
story.append(Image(str(DOC/'images/cad-perspective.png'),width=490,height=367.5))
story.append(Paragraph('<b>BENCH ONLY — NOT FOR WEAR.</b> Editable CAD and a testable hypothesis, not a clinically validated hearing aid. Useful acoustic gain and the $1 custom-device target remain unproven.',styles['Text']))
story.append(Paragraph('Inside: ear acoustics • parametric geometry • phone sizing • material and cost assumptions • durability and clinical gates • sources.',styles['Text']))
story.append(PageBreak())
lines=(DOC/'DESIGN.md').read_text().splitlines();i=0
while i<len(lines):
    line=lines[i].strip();i+=1
    if not line:continue
    if line.startswith('```'):
        block=[]
        while i<len(lines) and not lines[i].startswith('```'):block.append(lines[i]);i+=1
        i+=1
        for l in block:story.append(Paragraph(escape(l),styles['SmallText']))
        story.append(Spacer(1,10));continue
    if line.startswith('!['):
        path=re.search(r'\((.*?)\)',line).group(1)
        from PIL import Image as PILImage
        w,h=PILImage.open(DOC/path).size
        story.append(Image(str(DOC/path),width=490,height=490*h/w));story.append(Spacer(1,10));continue
    if line.startswith('|'):
        rows=[line]
        while i<len(lines) and lines[i].strip().startswith('|'):rows.append(lines[i].strip());i+=1
        cells=[]
        for row in rows:
            bits=[v.strip() for v in row.strip('|').split('|')]
            if all(re.fullmatch(r'[:\- ]+',b) for b in bits):continue
            cells.append([Paragraph(fmt(b),styles['SmallText']) for b in bits])
        widths=[310,180] if len(cells[0])==2 else None
        tab=Table(cells,colWidths=widths,repeatRows=1,hAlign='LEFT')
        tab.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dbe6dc')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,-1),.3,colors.HexColor('#cad4cd'))]));story.append(tab);story.append(Spacer(1,12));continue
    if line.startswith('#'):
        level=len(line)-len(line.lstrip('#'));story.append(Paragraph(fmt(line[level:].strip()),styles['Heading'+str(min(3,level))]));continue
    if line.startswith('- '):story.append(Paragraph('• '+fmt(line[2:]),styles['Text']));continue
    if re.match(r'^\d+\. ',line):story.append(Paragraph(fmt(line),styles['Text']));continue
    para=[line]
    while i<len(lines) and lines[i].strip() and not lines[i].startswith(('#','![','|','```','- ')):
        para.append(lines[i].strip());i+=1
    story.append(Paragraph(fmt(' '.join(para)),styles['Text']))

def footer(c,doc):
    c.setStrokeColor(colors.HexColor('#cad4cd'));c.line(45,42,550,42);c.setFont(regular,7);c.setFillColor(colors.HexColor('#52685b'));c.drawString(45,29,'PEBBLE P0 • Independent concept • No measured hearing benefit • Bench only');c.drawRightString(550,29,str(doc.page))
pdf=SimpleDocTemplate(str(DOC/'PEBBLE-P0.pdf'),pagesize=(595.28,841.89),leftMargin=50,rightMargin=50,topMargin=45,bottomMargin=56,title='PEBBLE P0 — Passive Earbud Research Concept',author='Khankindle project',pageCompression=1)
pdf.build(story,onFirstPage=footer,onLaterPages=footer)
print(DOC/'PEBBLE-P0.pdf')
