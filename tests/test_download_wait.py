from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from scripts.download_wait import wait_for_download
from scripts.browser_session import HumanWaitTimeout


URL='https://worldwide.espacenet.com/data/espacenetDocument.pdf?CC=JP&NR=2004121879A&KC=A&flavour=trueFull'


class Page:
    def __init__(self):
        self.listeners={}
        self.next_event=None
    def on(self,event,callback):self.listeners[event]=callback
    def remove_listener(self,event,callback):self.listeners.pop(event,None)
    def wait_for_timeout(self,ms):
        if self.next_event:
            action,self.next_event=self.next_event,None
            action()


def verification(url=URL):
    return SimpleNamespace(url=url,headers={'content-type':'text/html'},
        text=lambda:'<h1>Espacenet verification</h1>Please enter the digits')


class DownloadWait(TestCase):
    def test_download_completes_without_reclicking(self):
        page=Page();item=SimpleNamespace(url=URL);clicks=[]
        def trigger():
            clicks.append(1)
            page.listeners['response'](verification())
            page.next_event=lambda:page.listeners['download'](item)
        self.assertIs(wait_for_download(page,trigger,URL,5,True),item)
        self.assertEqual(len(clicks),1)
        self.assertEqual(page.listeners,{})

    def test_repeated_challenge_stops_without_auto_resubmit(self):
        page=Page();clicks=[]
        def trigger():
            clicks.append(1)
            for _ in range(3):page.listeners['response'](verification())
        with self.assertRaisesRegex(HumanWaitTimeout,'반복'):
            wait_for_download(page,trigger,URL,5,True)
        self.assertEqual(len(clicks),1)
        self.assertEqual(page.listeners,{})

    def test_other_publication_response_does_not_count_as_repeat(self):
        page=Page();item=SimpleNamespace(url=URL)
        def trigger():
            for _ in range(3):page.listeners['response'](verification(URL.replace('2004121879A','2006198019A')))
            page.next_event=lambda:page.listeners['download'](item)
        self.assertIs(wait_for_download(page,trigger,URL,5,True),item)

    def test_human_wait_is_bounded(self):
        page=Page()
        with patch('scripts.download_wait.time.monotonic',side_effect=[0,0,2]):
            with self.assertRaisesRegex(HumanWaitTimeout,'대기 시간 초과'):
                wait_for_download(page,lambda:None,URL,1,True)
        self.assertEqual(page.listeners,{})

    def test_prompt_counts_and_callback_are_recorded_without_answers(self):
        page=Page();metrics={};notices=[];item=SimpleNamespace(url=URL)
        def trigger():
            page.listeners['response'](verification())
            page.next_event=lambda:page.listeners['download'](item)
        self.assertIs(wait_for_download(page,trigger,URL,5,True,metrics=metrics,on_prompt=notices.append),item)
        self.assertEqual(notices,[1])
        self.assertEqual(metrics['captcha_prompts'],1)
        self.assertEqual(metrics['status'],'downloaded')
        self.assertNotIn('answer',metrics)

    def test_unrelated_download_is_ignored_until_exact_source_arrives(self):
        page=Page();metrics={};good=SimpleNamespace(url=URL)
        def trigger():
            for url in (URL.replace('2004121879A','2006198019A'),
                        URL.replace('worldwide.espacenet.com','example.org'),
                        URL.replace('trueFull','plainPage'),URL.replace('KC=A','KC=B'),
                        URL.replace('https:','http:')):
                page.listeners['download'](SimpleNamespace(url=url))
            page.next_event=lambda:page.listeners['download'](good)
        self.assertIs(wait_for_download(page,trigger,URL,5,True,metrics=metrics),good)
        self.assertEqual(metrics['ignored_downloads'],5)
