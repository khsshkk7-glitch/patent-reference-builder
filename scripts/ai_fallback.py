"""Render agent-reviewed translations; this module does not call an AI API."""
from html import escape
from pathlib import Path
import re
from urllib.parse import parse_qs, urlparse

from .browser_session import CollectionError, assert_official_url
from .collector_common import Collected, english_abstract
from .input_parser import one, resolve
from .pdf_merger import inspect_pdf, sha256

LABELS = {
    'ai_translation': ('AI TRANSLATION - NOT AN OFFICIAL ENGLISH ABSTRACT', 'AI 번역 보완'),
    'ai_summary': ('AI-GENERATED SUMMARY - NOT AN OFFICIAL ABSTRACT', 'AI 요약 보완'),
    'site_machine_translation': ('SITE MACHINE TRANSLATION - EPO PATENT TRANSLATE', '사이트 기계번역 보완'),
}


def validate_packet(requested, entry, base):
    publication = one(entry['publication'])
    if requested.role != 'publication' or not requested.kind or not publication.kind:
        raise CollectionError('AI 보완은 확정된 공보번호와 종별이 필요합니다.')
    resolve(requested, [publication])
    mode = entry.get('translation_type')
    if mode not in LABELS:
        raise CollectionError('AI 번역/요약 또는 사이트 기계번역 구분이 필요합니다.')
    has_abstract = entry.get('source_abstract_available')
    if (mode in ('ai_translation','site_machine_translation') and (has_abstract is not True or entry.get('source_kind') != 'abstract')) or (
        mode == 'ai_summary' and (has_abstract is not False or entry.get('source_kind') != 'description')):
        raise CollectionError('원문 초록 유무와 AI 번역/요약 종류가 일치하지 않습니다.')
    if mode == 'site_machine_translation':
        url = urlparse(entry.get('site_translation_url',''))
        query = parse_qs(url.query)
        if url.scheme!='https' or url.netloc!='translationportal.epo.org' or any(query.get(k)!=[v] for k,v in (
            ('COUNTRY',publication.country),('NUMBER',publication.number),('KIND',publication.kind),('TRGLANG','en'))):
            raise CollectionError('Patent Translate 출처의 공보번호·종별·영어 대상 언어 불일치')
        if query.get('apikey') or 'machine-generated' not in entry.get('site_translation_notice','') or entry.get('site_translation_verified') is not True:
            raise CollectionError('사이트 번역 고지·직접 확인 기록 누락 또는 불필요한 키 포함')
    for key in ('identity_verified', 'full_document_verified', 'source_text_verified', 'translation_reviewed'):
        if entry.get(key) is not True:
            raise CollectionError('AI 보완 검토 기록 누락: '+key)
    for key in ('source_language', 'source_text', 'review_note', 'official_english_unavailable_reason'):
        if not str(entry.get(key, '')).strip():
            raise CollectionError('AI 보완 근거 누락: '+key)
    if entry['source_language'].lower() in ('en', 'english'):
        raise CollectionError('영문 원문을 비영문 번역으로 표시할 수 없습니다.')
    source = entry['original_source']
    if source not in ('Espacenet', 'KIPRIS'):
        raise CollectionError('공식 원문 출처는 Espacenet/KIPRIS여야 합니다.')
    assert_official_url(entry['original_url'], source)
    if source == 'Espacenet':
        query = parse_qs(urlparse(entry['original_url']).query)
        for key, expected in (('CC',publication.country), ('NR',publication.number+publication.kind), ('KC',publication.kind)):
            if key in query and query[key] != [expected]:
                raise CollectionError('AI 보완 원문 URL의 공보번호/종별 불일치')
    path = Path(base) / entry['original_pdf']
    if entry.get('original_sha256') != sha256(path):
        raise CollectionError('AI 보완 원문 SHA-256 불일치')
    reader = inspect_pdf(path)
    count = entry['original_pages']
    if type(count) is not int or len(reader.pages) != count or entry.get('viewer_pages') != count:
        raise CollectionError('AI 보완 원문·뷰어 전체 페이지 수 불일치')
    pages = entry.get('source_pages', [])
    if not pages or any(type(n) is not int or not 1 <= n <= count for n in pages):
        raise CollectionError('AI 번역/요약의 근거 페이지가 필요합니다.')
    english_abstract(entry['english_abstract'])
    bibliography = entry.get('bibliography', [])
    required = {'Publication', 'Title', 'Applicant / Right holder', 'Inventor / Creator'}
    if not isinstance(bibliography, list) or not all(isinstance(row, list) and len(row)==2 and all(isinstance(x,str) and x.strip() for x in row) for row in bibliography):
        raise CollectionError('영문 서지사항 형식 오류')
    rows = dict(bibliography)
    if not required.issubset(rows) or re.sub(r'[^A-Z0-9]', '', rows['Publication'].upper()) != publication.key:
        raise CollectionError('영문 서지사항 필수 항목 또는 공보번호 불일치')
    figure = entry.get('figure')
    if figure:
        box = figure.get('box', [])
        if type(figure.get('page')) is not int or not 1 <= figure['page'] <= count or len(box)!=4 or not (0<=box[0]<box[2]<=1 and 0<=box[1]<box[3]<=1):
            raise CollectionError('대표도면 원문 위치 오류')
    return publication, path, count


def render_front(entry, original, output):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    label = LABELS[entry['translation_type']][0]
    style = ParagraphStyle('body', fontName='Helvetica', fontSize=9, leading=12, spaceAfter=5)
    small = ParagraphStyle('small', parent=style, fontSize=7, leading=9)
    heading = ParagraphStyle('heading', parent=style, fontName='Helvetica-Bold', fontSize=11, leading=14)
    para = lambda text, s=style: Paragraph(escape(text).replace('\n','<br/>'), s)
    site = entry['translation_type']=='site_machine_translation'
    info = ('Bibliography: AI translations/romanizations of the original. Abstract: site-provided EPO Patent Translate (Google); not AI-authored.' if site else 'AI-prepared bibliographic sheet. The English text below is not supplied or certified by a patent office.')
    story = [para(label, heading), para(info, small), Spacer(1,3*mm)]
    rows = [[para(k), para(v)] for k,v in entry['bibliography']]
    table = Table(rows, colWidths=[43*mm,135*mm], hAlign='LEFT')
    table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(0,-1),colors.HexColor('#eef1f4')),
        ('LINEBELOW',(0,0),(-1,-1),0.3,colors.HexColor('#ccd1d6')),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5)]))
    abstract_heading = 'Site-provided machine-translated abstract' if site else ('AI-translated abstract' if entry['translation_type']=='ai_translation' else 'AI-generated English summary')
    story += [table, Spacer(1,4*mm), para(abstract_heading,heading), para(entry['english_abstract'])]
    if site:
        story += [para(entry['site_translation_notice'],small),para('Translation source: '+entry['site_translation_url'],small)]
    if entry.get('figure'):
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument(original)
        page = doc[entry['figure']['page']-1]
        bitmap = page.render(scale=2)
        image = bitmap.to_pil()
        x0,y0,x1,y1 = entry['figure']['box']
        crop = image.crop((int(x0*image.width),int(y0*image.height),int(x1*image.width),int(y1*image.height)))
        fig = output.with_suffix('.figure.png')
        crop.save(fig)
        width = min(65*mm, 70*mm*crop.width/crop.height)
        height = width*crop.height/crop.width
        story += [Spacer(1,2*mm), para('Representative drawing (unaltered crop of the original)',small), Image(str(fig), width=width,height=height,hAlign='LEFT')]
        page.close(); doc.close()
    story += [Spacer(1,3*mm), para('Source: '+entry['original_url'],small),
        para('Source language: '+entry['source_language']+'; source PDF page(s): '+', '.join(map(str,entry['source_pages']))+'. Original publication follows this sheet in full.',small),
        para('Bibliographic notes: '+entry.get('bibliography_note','AI-rendered English fields checked against the original publication.'),small)]
    def footer(canvas, doc):
        canvas.setFont('Helvetica',6)
        canvas.drawString(16*mm,10*mm,entry['publication']+' | '+label+' | '+str(doc.page))
    SimpleDocTemplate(str(output), pagesize=A4, rightMargin=16*mm,leftMargin=16*mm,topMargin=14*mm,bottomMargin=16*mm,
        title=entry['publication']+' - AI-assisted reference',subject=label).build(story,onFirstPage=footer,onLaterPages=footer)
    normalize = lambda s: re.sub(r'\s+', '', s)
    reader = inspect_pdf(output)
    printed = ''.join(p.extract_text() or '' for p in reader.pages)
    if normalize(entry['english_abstract']) not in normalize(printed) or label not in printed:
        raise CollectionError('AI 인쇄본에 전체 번역문 또는 고지 누락')
    if site and normalize(entry['site_translation_notice']) not in normalize(printed):
        raise CollectionError('Patent Translate 인쇄본의 기계번역 고지 누락')


def from_ai_packet(requested, entry, base, work):
    publication, original, count = validate_packet(requested, entry, base)
    biblio = Path(work)/'ai-bibliography.pdf'
    render_front(entry, original, biblio)
    mode = entry['translation_type']
    provenance = {k:entry[k] for k in ('translation_type','source_language','source_kind','source_pages',
        'source_text','english_abstract','official_english_unavailable_reason','review_note')}
    provenance['bibliography'] = entry['bibliography']
    provenance['bibliography_note'] = entry.get('bibliography_note','')
    if mode=='site_machine_translation':
        provenance.update({k:entry[k] for k in ('site_translation_url','site_translation_notice','site_translation_verified')})
    source_suffix = ' + EPO Patent Translate / AI bibliography' if mode=='site_machine_translation' else ' + AI'
    return Collected(publication,biblio,original,count,entry['original_source']+source_suffix,entry.get('site_translation_url',entry['original_url']),entry['original_url'],
        LABELS[mode][1]+'; 공식 영문 초록 아님; 동일 공보 원문 근거 대조; '+entry['review_note'],(),mode,provenance)
