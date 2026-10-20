"""EPO's supported API for complete official page images; no CAPTCHA solving."""
import base64
import io
import json
import os
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler
import xml.etree.ElementTree as ET

from .browser_session import CollectionError
from .pdf_merger import inspect_pdf, sha256

BASE = 'https://ops.epo.org/3.2/rest-services/'
TOKEN = 'https://ops.epo.org/3.2/auth/accesstoken'


def configured():
    return bool(os.getenv('EPO_OPS_KEY') and os.getenv('EPO_OPS_SECRET'))


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_bytes(url, headers, data=None, timeout=40):
    try:
        with build_opener(NoRedirect).open(Request(url,headers=headers,data=data),timeout=timeout) as response:
            body = response.read(20*1024*1024+1)
            if len(body)>20*1024*1024:
                raise CollectionError('OPS 응답 크기 제한 초과')
            return body
    except HTTPError as exc:
        # Never echo request headers, token responses or credentials.
        raise CollectionError(f'OPS HTTP {exc.code}: 인증·이용량·서비스 상태를 확인하세요. 자동 재시도하지 않습니다.') from None
    except (URLError, TimeoutError):
        raise CollectionError('OPS 네트워크 연결 실패 또는 시간 초과') from None


def full_image(xml, publication):
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        raise CollectionError('OPS 문헌 정보 XML 오류') from None
    expected = f'{publication.country}/{publication.number}/{publication.kind}/fullimage'
    found = []
    for node in root.iter():
        if node.tag.split('}')[-1] != 'document-instance':
            continue
        link = node.get('link','')
        # Some official responses prefix the image path with published-data/images/.
        link = link.removeprefix('published-data/images/')
        formats = [''.join(e.itertext()).strip() for e in node.iter() if e.tag.split('}')[-1]=='document-format']
        if link == expected and node.get('desc') == 'FullDocument' and 'application/pdf' in formats:
            try:
                count = int(node.get('number-of-pages','0'))
            except ValueError:
                raise CollectionError('OPS 전체 페이지 수 오류') from None
            if not 1 <= count <= 1000:
                raise CollectionError('OPS 전체 페이지 수 확인 필요 (허용 범위 1~1000)')
            found.append((link,count))
    if len(found)!=1:
        raise CollectionError('OPS에 동일 공보번호·종별의 PDF 전문이 없거나 단일하지 않습니다.')
    return found[0]


class OpsClient:
    def __init__(self, timeout=40, transport=request_bytes):
        self.timeout, self.transport = timeout, transport
        self.token, self.expires, self.next_request = None, 0, 0

    def authenticate(self):
        if not configured():
            raise CollectionError('OPS API 키 미설정: EPO_OPS_KEY/EPO_OPS_SECRET을 로컬 환경에 설정하세요. 키를 채팅에 보내지 마세요.')
        if self.token and time.monotonic()<self.expires:
            return
        basic = base64.b64encode((os.environ['EPO_OPS_KEY']+':'+os.environ['EPO_OPS_SECRET']).encode()).decode()
        raw = self.transport(TOKEN, {'Authorization':'Basic '+basic, 'Content-Type':'application/x-www-form-urlencoded'},
            data=b'grant_type=client_credentials', timeout=self.timeout)
        try:
            data = json.loads(raw)
            self.token = data['access_token']
            lifetime = int(data['expires_in'])
            if not isinstance(self.token,str) or not self.token or lifetime<=0:
                raise ValueError()
        except (ValueError,KeyError,TypeError):
            raise CollectionError('OPS 인증 응답 형식 오류 (응답 본문은 기록하지 않음)') from None
        self.expires = time.monotonic()+max(0,lifetime-30)

    def get(self, path, accept):
        while time.monotonic()<self.next_request:
            time.sleep(max(0,min(30,self.next_request-time.monotonic())))
        self.authenticate()
        body = self.transport(BASE+path, {'Authorization':'Bearer '+self.token, 'Accept':accept},timeout=self.timeout)
        # Sequential requests; keep average transfer below approx. 1 Mbit/s.
        self.next_request = time.monotonic()+max(.5,len(body)/100000)
        return body

    def download(self, publication, work, expected_pages=None):
        if not publication.kind or publication.role!='publication':
            raise CollectionError('OPS 수집은 확정된 공보번호·종별이 필요합니다.')
        self.authenticate()  # No request at all when credentials are missing.
        work = Path(work)
        work.mkdir(parents=True,exist_ok=True)
        path = f'published-data/publication/docdb/{publication.country}.{publication.number}.{publication.kind}/images'
        xml = self.get(path,'application/xml')
        link,count = full_image(xml,publication)
        if expected_pages is not None and count!=expected_pages:
            raise CollectionError(f'OPS 전문 {count}페이지와 Espacenet 뷰어 {expected_pages}페이지 불일치')
        (work/'ops-images.xml').write_bytes(xml)
        from pypdf import PdfReader, PdfWriter
        writer = PdfWriter()
        hashes=[]
        try:
            for number in range(1,count+1):
                data = self.get('published-data/images/'+link+'.pdf?Range='+str(number),'application/pdf')
                if not data.startswith(b'%PDF-'):
                    raise CollectionError(f'OPS {number}페이지가 PDF가 아닙니다.')
                reader = PdfReader(io.BytesIO(data))
                if reader.is_encrypted or len(reader.pages)!=1:
                    raise CollectionError(f'OPS {number}페이지 응답이 단일 공보 페이지가 아닙니다.')
                page_file = work/f'ops-page-{number:04d}.pdf'
                page_file.write_bytes(data)
                hashes.append(sha256(page_file))
                writer.append(reader)
            output = work/'original-ops.pdf'
            writer.write(output)
        finally:
            writer.close()
        if len(inspect_pdf(output).pages)!=count:
            raise CollectionError('OPS 페이지 조립 후 총 페이지 수 불일치')
        source_url = BASE+path
        evidence = dict(publication=publication.key,source='EPO OPS',source_url=source_url,
            pages=count,page_sha256=hashes,sha256=sha256(output),assembly='Official single-page PDFs in API order; no content translation',
            captcha_prompts=0)
        (work/'ops-download.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
        return output,count,source_url
